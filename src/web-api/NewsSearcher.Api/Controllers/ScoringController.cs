using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using NewsSearcher.Api.Services;

namespace NewsSearcher.Api.Controllers;

[ApiController]
[Route("api/[controller]")]
[Authorize]
public class ScoringController : ControllerBase
{
    private readonly MlServiceClient _ml;

    public ScoringController(MlServiceClient ml)
    {
        _ml = ml;
    }

    [HttpPost("trigger")]
    public async Task<IActionResult> Trigger()
    {
        var result = await _ml.TriggerScoringAsync();
        return Ok(result);
    }

    [HttpGet("status")]
    public async Task<IActionResult> GetStatus()
    {
        var result = await _ml.GetScoringStatusAsync();
        return Ok(result);
    }
}
