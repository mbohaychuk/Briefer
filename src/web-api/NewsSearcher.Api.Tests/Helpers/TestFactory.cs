using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.Data.Sqlite;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using NewsSearcher.Api.Data;

namespace NewsSearcher.Api.Tests.Helpers;

public class TestFactory : WebApplicationFactory<Program>
{
    // Keep the connection open so the in-memory SQLite DB persists
    // across scoped DbContext instances (one per HTTP request)
    private readonly SqliteConnection _connection = new("DataSource=:memory:");

    protected override void ConfigureWebHost(IWebHostBuilder builder)
    {
        _connection.Open();

        builder.ConfigureServices(services =>
        {
            // Remove all DbContext option registrations to avoid
            // dual-provider conflict with Npgsql from Program.cs
            var descriptorsToRemove = services.Where(d =>
                d.ServiceType == typeof(AppDbContext)
                || d.ServiceType.FullName?.Contains("DbContextOptions") == true
            ).ToList();

            foreach (var descriptor in descriptorsToRemove)
                services.Remove(descriptor);

            services.AddDbContext<AppDbContext>(options =>
                options.UseSqlite(_connection)
                       .UseSnakeCaseNamingConvention());
        });

        builder.UseEnvironment("Testing");
    }

    protected override void Dispose(bool disposing)
    {
        base.Dispose(disposing);
        _connection.Dispose();
    }
}
