using System.Security.Claims;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using NewsSearcher.Api.Data;
using NewsSearcher.Api.Models.DTOs.Profile;
using NewsSearcher.Api.Models.Entities;
using NewsSearcher.Api.Services;

namespace NewsSearcher.Api.Controllers;

[ApiController]
[Route("api/[controller]")]
[Authorize]
public class ProfileController : ControllerBase
{
    private readonly AppDbContext _db;
    private readonly MlServiceClient _ml;
    private readonly ILogger<ProfileController> _logger;

    public ProfileController(AppDbContext db, MlServiceClient ml, ILogger<ProfileController> logger)
    {
        _db = db;
        _ml = ml;
        _logger = logger;
    }

    private string UserId => User.FindFirstValue(ClaimTypes.NameIdentifier)!;

    [HttpGet]
    public async Task<IActionResult> GetProfile()
    {
        var profile = await _db.UserProfiles
            .Include(p => p.Interests.OrderBy(i => i.SortOrder))
            .FirstOrDefaultAsync(p => p.UserId == UserId && p.IsCurrent);

        if (profile == null)
            return NotFound();

        return Ok(new ProfileResponse
        {
            Version = profile.Version,
            Interests = profile.Interests.Select(i => new InterestDescriptionDto
            {
                Id = i.Id,
                Title = i.Title,
                Description = i.Description,
                SortOrder = i.SortOrder
            }).ToList()
        });
    }

    [HttpPost("interests")]
    public async Task<IActionResult> AddInterest(CreateInterestRequest request)
    {
        var (newProfile, _) = PrepareNewProfileVersion();

        var maxOrder = newProfile.Interests.Any()
            ? newProfile.Interests.Max(i => i.SortOrder)
            : -1;

        var interest = new InterestDescription
        {
            UserProfileId = newProfile.Id,
            Title = request.Title,
            Description = request.Description,
            SortOrder = maxOrder + 1
        };
        newProfile.Interests.Add(interest);
        await _db.SaveChangesAsync();
        await SyncProfileToMlServiceAsync();

        return Ok(new InterestDescriptionDto
        {
            Id = interest.Id,
            Title = interest.Title,
            Description = interest.Description,
            SortOrder = interest.SortOrder
        });
    }

    [HttpPut("interests/{interestId:guid}")]
    public async Task<IActionResult> UpdateInterest(Guid interestId, UpdateInterestRequest request)
    {
        var (newProfile, idMapping) = PrepareNewProfileVersion();

        var mappedId = ResolveInterestId(interestId, idMapping);
        var interest = newProfile.Interests.FirstOrDefault(i => i.Id == mappedId);
        if (interest == null)
            return NotFound();

        interest.Title = request.Title;
        interest.Description = request.Description;
        if (request.SortOrder.HasValue)
            interest.SortOrder = request.SortOrder.Value;

        await _db.SaveChangesAsync();
        await SyncProfileToMlServiceAsync();

        return Ok(new InterestDescriptionDto
        {
            Id = interest.Id,
            Title = interest.Title,
            Description = interest.Description,
            SortOrder = interest.SortOrder
        });
    }

    [HttpDelete("interests/{interestId:guid}")]
    public async Task<IActionResult> DeleteInterest(Guid interestId)
    {
        var (newProfile, idMapping) = PrepareNewProfileVersion();

        var mappedId = ResolveInterestId(interestId, idMapping);
        var interest = newProfile.Interests.FirstOrDefault(i => i.Id == mappedId);
        if (interest == null)
            return NotFound();

        newProfile.Interests.Remove(interest);
        _db.InterestDescriptions.Remove(interest);
        await _db.SaveChangesAsync();
        await SyncProfileToMlServiceAsync();

        return NoContent();
    }

    private static Guid ResolveInterestId(Guid clientId, Dictionary<Guid, Guid> idMapping)
    {
        return idMapping.TryGetValue(clientId, out var newId) ? newId : clientId;
    }

    /// <summary>
    /// Creates a new profile version by copying from the current one.
    /// Does NOT save — the caller saves once after making its changes.
    /// Returns the new profile and an old-to-new interest ID mapping.
    /// </summary>
    private (UserProfile Profile, Dictionary<Guid, Guid> IdMapping) PrepareNewProfileVersion()
    {
        var currentProfile = _db.UserProfiles
            .Include(p => p.Interests)
            .First(p => p.UserId == UserId && p.IsCurrent);

        currentProfile.IsCurrent = false;

        var newProfile = new UserProfile
        {
            UserId = UserId,
            Version = currentProfile.Version + 1,
            IsCurrent = true
        };

        var idMapping = new Dictionary<Guid, Guid>();

        foreach (var interest in currentProfile.Interests)
        {
            var newInterest = new InterestDescription
            {
                UserProfileId = newProfile.Id,
                Title = interest.Title,
                Description = interest.Description,
                SortOrder = interest.SortOrder
            };
            newProfile.Interests.Add(newInterest);
            idMapping[interest.Id] = newInterest.Id;
        }

        _db.UserProfiles.Add(newProfile);

        return (newProfile, idMapping);
    }

    /// <summary>
    /// Push the current user's profile to the ML service so it can
    /// re-embed interest blocks for scoring and briefing.
    /// Failures are logged but do not block the HTTP response.
    /// </summary>
    private async Task SyncProfileToMlServiceAsync()
    {
        try
        {
            var user = await _db.Users.FindAsync(UserId);
            var profile = await _db.UserProfiles
                .Include(p => p.Interests.OrderBy(i => i.SortOrder))
                .FirstOrDefaultAsync(p => p.UserId == UserId && p.IsCurrent);

            if (profile == null || user == null)
                return;

            var payload = new
            {
                profiles = new[]
                {
                    new
                    {
                        user_id = UserId,
                        name = user.Email ?? "Unknown",
                        interests = profile.Interests.Select(i => new
                        {
                            label = i.Title,
                            text = i.Description,
                        }).ToArray(),
                    }
                }
            };

            await _ml.SyncProfilesAsync(payload);
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Failed to sync profile to ML service for user {UserId}", UserId);
        }
    }
}
