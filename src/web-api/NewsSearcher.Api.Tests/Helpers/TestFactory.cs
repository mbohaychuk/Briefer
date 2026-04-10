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

    /// <summary>
    /// Shared mock handler that all tests in this fixture can configure.
    /// Registered as the primary handler for the "MlService" named HttpClient.
    /// </summary>
    public MockHttpHandler MlHandler { get; } = CreateDefaultHandler();

    private static MockHttpHandler CreateDefaultHandler()
    {
        var handler = new MockHttpHandler();
        // Profile sync is triggered by ProfileController mutations;
        // register a default OK so tests don't hit retry delays.
        handler.RegisterOk("POST", "/api/profiles/sync",
            """{"status":"ok","profiles_synced":1}""");
        return handler;
    }

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

            // Replace the "MlService" HttpClient with one backed by MockHttpHandler
            services.AddHttpClient("MlService")
                .ConfigurePrimaryHttpMessageHandler(() => MlHandler);
        });

        builder.UseEnvironment("Testing");
    }

    protected override void Dispose(bool disposing)
    {
        base.Dispose(disposing);
        _connection.Dispose();
    }
}
