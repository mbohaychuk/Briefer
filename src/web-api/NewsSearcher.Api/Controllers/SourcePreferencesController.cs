using System.Security.Claims;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using NewsSearcher.Api.Data;
using NewsSearcher.Api.Models.DTOs.SourcePreference;
using NewsSearcher.Api.Models.Entities;

namespace NewsSearcher.Api.Controllers;

[ApiController]
[Route("api/[controller]")]
[Authorize]
public class SourcePreferencesController : ControllerBase
{
    private static readonly List<(PreferenceType Type, string Target)> SystemDefaults =
    [
        (PreferenceType.Blocklist, "theonion.com"),
        (PreferenceType.Blocklist, "babylonbee.com"),
        (PreferenceType.Blocklist, "clickhole.com"),
        (PreferenceType.Blocklist, "waterfordwhispersnews.com"),
    ];

    private readonly AppDbContext _db;

    public SourcePreferencesController(AppDbContext db)
    {
        _db = db;
    }

    private string UserId => User.FindFirstValue(ClaimTypes.NameIdentifier)!;

    [HttpGet]
    public async Task<IActionResult> GetPreferences()
    {
        var userPrefs = await _db.SourcePreferences
            .Where(s => s.UserId == UserId)
            .ToListAsync();

        var systemPrefs = SystemDefaults.Select(d => new SourcePreferenceDto
        {
            Id = Guid.Empty,
            Type = d.Type.ToString(),
            Target = d.Target,
            IsSystemDefault = true
        });

        var userPrefDtos = userPrefs.Select(s => new SourcePreferenceDto
        {
            Id = s.Id,
            Type = s.Type.ToString(),
            Target = s.Target,
            IsSystemDefault = false
        });

        return Ok(systemPrefs.Concat(userPrefDtos));
    }

    [HttpPost]
    public async Task<IActionResult> AddPreference(CreateSourcePreferenceRequest request)
    {
        if (!Enum.TryParse<PreferenceType>(request.Type, true, out var prefType))
            return BadRequest(new { error = "Type must be 'Blocklist' or 'Priority'" });

        var pref = new SourcePreference
        {
            UserId = UserId,
            Type = prefType,
            Target = request.Target.ToLowerInvariant(),
            IsSystemDefault = false
        };

        _db.SourcePreferences.Add(pref);
        await _db.SaveChangesAsync();

        return Ok(new SourcePreferenceDto
        {
            Id = pref.Id,
            Type = pref.Type.ToString(),
            Target = pref.Target,
            IsSystemDefault = false
        });
    }

    [HttpDelete("{id:guid}")]
    public async Task<IActionResult> DeletePreference(Guid id)
    {
        var pref = await _db.SourcePreferences
            .FirstOrDefaultAsync(s => s.Id == id && s.UserId == UserId);

        if (pref == null)
            return NotFound();

        _db.SourcePreferences.Remove(pref);
        await _db.SaveChangesAsync();

        return NoContent();
    }
}
