using System.ComponentModel.DataAnnotations;

namespace Briefer.Api.Models.DTOs.Profile;

public class CreateInterestRequest
{
    [Required, MaxLength(200)]
    public string Title { get; set; } = null!;

    [Required, MaxLength(5000)]
    public string Description { get; set; } = null!;
}
