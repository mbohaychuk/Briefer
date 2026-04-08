using System.ComponentModel.DataAnnotations;

namespace NewsSearcher.Api.Models.DTOs.Auth;

public class RegisterRequest
{
    [Required, EmailAddress]
    public string Email { get; set; } = null!;

    [Required, MinLength(8)]
    public string Password { get; set; } = null!;
}
