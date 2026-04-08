using Microsoft.AspNetCore.Identity;

namespace NewsSearcher.Api.Models.Entities;

public class ApplicationUser : IdentityUser
{
    public int CurrentProfileVersion { get; set; } = 1;
    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;

    public ICollection<UserProfile> Profiles { get; set; } = [];
    public ICollection<SourcePreference> SourcePreferences { get; set; } = [];
}
