using System.Security.Claims;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using NewsSearcher.Api.Data;
using NewsSearcher.Api.Models.DTOs.Profile;
using NewsSearcher.Api.Models.Entities;

namespace NewsSearcher.Api.Controllers;

[ApiController]
[Route("api/[controller]")]
[Authorize]
public class ProfileController : ControllerBase
{
    private readonly AppDbContext _db;

    public ProfileController(AppDbContext db)
    {
        _db = db;
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
}
