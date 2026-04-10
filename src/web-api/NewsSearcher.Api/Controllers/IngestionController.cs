using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using NewsSearcher.Api.Services;

namespace NewsSearcher.Api.Controllers;

[ApiController]
[Route("api/[controller]")]
[Authorize]
public class IngestionController : ControllerBase
{
    private readonly MlServiceClient _ml;

    public IngestionController(MlServiceClient ml)
    {
        _ml = ml;
    }

    [HttpPost("trigger")]
    public async Task<IActionResult> Trigger()
    {
        var result = await _ml.TriggerIngestionAsync();
        return Ok(result);
    }

    [HttpGet("status")]
    public async Task<IActionResult> GetStatus()
    {
        var result = await _ml.GetIngestionStatusAsync();
        return Ok(result);
    }

    [HttpGet("feeds")]
    public async Task<IActionResult> GetFeeds()
    {
        var result = await _ml.GetFeedsAsync();
        return Ok(result);
    }
}
