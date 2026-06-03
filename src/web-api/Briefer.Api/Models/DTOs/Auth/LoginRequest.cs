using System.ComponentModel.DataAnnotations;

namespace Briefer.Api.Models.DTOs.Auth;

public class LoginRequest
{
    [Required, EmailAddress]
    public string Email { get; set; } = null!;

    [Required]
    public string Password { get; set; } = null!;
}
