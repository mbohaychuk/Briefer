using System.ComponentModel.DataAnnotations;

namespace NewsSearcher.Api.Models.DTOs.Profile;

public class UpdateInterestRequest
{
    [Required, MaxLength(200)]
    public string Title { get; set; } = null!;

    [Required, MaxLength(5000)]
    public string Description { get; set; } = null!;

    public int? SortOrder { get; set; }
}
