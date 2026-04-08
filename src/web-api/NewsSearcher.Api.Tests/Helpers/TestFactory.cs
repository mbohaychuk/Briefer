using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using NewsSearcher.Api.Data;

namespace NewsSearcher.Api.Tests.Helpers;

public class TestFactory : WebApplicationFactory<Program>
{
    protected override void ConfigureWebHost(IWebHostBuilder builder)
    {
        builder.ConfigureServices(services =>
        {
            // Remove all DbContext options registrations to avoid dual-provider
            // conflict between Npgsql (from Program.cs) and InMemory (test)
            var descriptorsToRemove = services.Where(d =>
                d.ServiceType == typeof(AppDbContext)
                || d.ServiceType.FullName?.Contains("DbContextOptions") == true
            ).ToList();

            foreach (var descriptor in descriptorsToRemove)
                services.Remove(descriptor);

            // Capture DB name OUTSIDE the lambda — Guid.NewGuid() inside
            // would create a different database per request
            var dbName = "TestDb_" + Guid.NewGuid();
            services.AddDbContext<AppDbContext>(options =>
                options.UseInMemoryDatabase(dbName));
        });

        builder.UseEnvironment("Testing");
    }
}
