using System.ComponentModel.DataAnnotations;

namespace NewsSearcher.Api.Models.DTOs.SourcePreference;

public class CreateSourcePreferenceRequest
{
    [Required]
    public string Type { get; set; } = null!;

    [Required, MaxLength(500)]
    public string Target { get; set; } = null!;
}
