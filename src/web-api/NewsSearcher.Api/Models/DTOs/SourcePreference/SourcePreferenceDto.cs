namespace NewsSearcher.Api.Models.DTOs.SourcePreference;

public class SourcePreferenceDto
{
    public Guid Id { get; set; }
    public string Type { get; set; } = null!;
    public string Target { get; set; } = null!;
    public bool IsSystemDefault { get; set; }
}
