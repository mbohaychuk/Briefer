using System.Security.Claims;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using NewsSearcher.Api.Services;

namespace NewsSearcher.Api.Controllers;

[ApiController]
[Route("api/[controller]")]
[Authorize]
public class BriefingController : ControllerBase
{
    private readonly MlServiceClient _ml;

    public BriefingController(MlServiceClient ml)
    {
        _ml = ml;
    }

    private string UserId => User.FindFirstValue(ClaimTypes.NameIdentifier)!;

    [HttpPost("generate")]
    public async Task<IActionResult> Generate()
    {
        var result = await _ml.GenerateBriefingAsync(UserId);
        return Ok(result);
    }

    [HttpGet("latest")]
    public async Task<IActionResult> GetLatest()
    {
        var result = await _ml.GetLatestBriefingAsync(UserId);
        if (result == null)
            return NotFound(new { error = "No briefings found" });
        return Ok(result);
    }

    [HttpGet("history")]
    public async Task<IActionResult> GetHistory([FromQuery] int limit = 30)
    {
        var result = await _ml.GetBriefingHistoryAsync(UserId, limit);
        return Ok(result);
    }

    [HttpGet("{briefingId}")]
    public async Task<IActionResult> GetById(string briefingId)
    {
        var result = await _ml.GetBriefingByIdAsync(briefingId);
        if (result == null)
            return NotFound(new { error = "Briefing not found" });
        return Ok(result);
    }
}
