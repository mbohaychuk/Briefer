namespace NewsSearcher.Api.Models.Entities;

public enum PreferenceType
{
    Blocklist,
    Priority
}

public class SourcePreference
{
    public Guid Id { get; set; } = Guid.NewGuid();
    public string? UserId { get; set; }
    public PreferenceType Type { get; set; }
    public string Target { get; set; } = null!;
    public bool IsSystemDefault { get; set; }
    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;

    public ApplicationUser? User { get; set; }
}
