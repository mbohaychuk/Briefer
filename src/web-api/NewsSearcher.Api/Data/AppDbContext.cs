using Microsoft.AspNetCore.Identity.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore;
using NewsSearcher.Api.Models.Entities;

namespace NewsSearcher.Api.Data;

public class AppDbContext : IdentityDbContext<ApplicationUser>
{
    public AppDbContext(DbContextOptions<AppDbContext> options) : base(options) { }

    public DbSet<UserProfile> UserProfiles => Set<UserProfile>();
    public DbSet<InterestDescription> InterestDescriptions => Set<InterestDescription>();
    public DbSet<SourcePreference> SourcePreferences => Set<SourcePreference>();

    protected override void OnModelCreating(ModelBuilder builder)
    {
        base.OnModelCreating(builder);

        builder.Entity<UserProfile>(e =>
        {
            e.HasIndex(p => new { p.UserId, p.Version }).IsUnique();
            e.HasIndex(p => new { p.UserId, p.IsCurrent })
                .HasFilter("is_current = true")
                .IsUnique();
        });

        builder.Entity<InterestDescription>(e =>
        {
            e.HasIndex(i => new { i.UserProfileId, i.SortOrder });
        });

        builder.Entity<SourcePreference>(e =>
        {
            e.HasIndex(s => new { s.UserId, s.Type, s.Target }).IsUnique();
        });
    }
}
