using System.Net.Http.Json;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace NewsSearcher.Api.Services;

public class MlServiceClient
{
    private readonly HttpClient _client;

    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
    };

    public MlServiceClient(IHttpClientFactory clientFactory)
    {
        _client = clientFactory.CreateClient("MlService");
    }

    // ── Health ──────────────────────────────────────────────────────

    public async Task<bool> IsHealthyAsync()
    {
        try
        {
            var response = await _client.GetAsync("/health");
            return response.IsSuccessStatusCode;
        }
        catch
        {
            return false;
        }
    }

    // ── Ingestion ───────────────────────────────────────────────────

    public async Task<JsonElement> TriggerIngestionAsync()
    {
        var response = await _client.PostAsync("/api/ingestion/trigger", null);
        response.EnsureSuccessStatusCode();
        return await response.Content.ReadFromJsonAsync<JsonElement>(JsonOptions);
    }

    public async Task<JsonElement> GetIngestionStatusAsync()
    {
        var response = await _client.GetAsync("/api/ingestion/status");
        response.EnsureSuccessStatusCode();
        return await response.Content.ReadFromJsonAsync<JsonElement>(JsonOptions);
    }

    public async Task<JsonElement> GetFeedsAsync()
    {
        var response = await _client.GetAsync("/api/ingestion/feeds");
        response.EnsureSuccessStatusCode();
        return await response.Content.ReadFromJsonAsync<JsonElement>(JsonOptions);
    }

    // ── Scoring ─────────────────────────────────────────────────────

    public async Task<JsonElement> TriggerScoringAsync()
    {
        var response = await _client.PostAsync("/api/scoring/trigger", null);
        response.EnsureSuccessStatusCode();
        return await response.Content.ReadFromJsonAsync<JsonElement>(JsonOptions);
    }

    public async Task<JsonElement> GetScoringStatusAsync()
    {
        var response = await _client.GetAsync("/api/scoring/status");
        response.EnsureSuccessStatusCode();
        return await response.Content.ReadFromJsonAsync<JsonElement>(JsonOptions);
    }

    // ── Briefing ────────────────────────────────────────────────────

    public async Task<JsonElement> GenerateBriefingAsync(string userId)
    {
        var response = await _client.PostAsync(
            $"/api/briefing/generate?user_id={Uri.EscapeDataString(userId)}", null);
        response.EnsureSuccessStatusCode();
        return await response.Content.ReadFromJsonAsync<JsonElement>(JsonOptions);
    }

    public async Task<JsonElement?> GetLatestBriefingAsync(string userId)
    {
        var response = await _client.GetAsync(
            $"/api/briefing/latest/{Uri.EscapeDataString(userId)}");

        if (response.StatusCode == System.Net.HttpStatusCode.NotFound)
            return null;

        response.EnsureSuccessStatusCode();
        return await response.Content.ReadFromJsonAsync<JsonElement>(JsonOptions);
    }

    public async Task<JsonElement> GetBriefingHistoryAsync(string userId, int limit = 30)
    {
        var response = await _client.GetAsync(
            $"/api/briefing/history/{Uri.EscapeDataString(userId)}?limit={limit}");
        response.EnsureSuccessStatusCode();
        return await response.Content.ReadFromJsonAsync<JsonElement>(JsonOptions);
    }

    public async Task<JsonElement?> GetBriefingByIdAsync(string briefingId)
    {
        var response = await _client.GetAsync(
            $"/api/briefing/{Uri.EscapeDataString(briefingId)}");

        if (response.StatusCode == System.Net.HttpStatusCode.NotFound)
            return null;

        response.EnsureSuccessStatusCode();
        return await response.Content.ReadFromJsonAsync<JsonElement>(JsonOptions);
    }

    // ── Profile Sync ────────────────────────────────────────────────

    public async Task<JsonElement> SyncProfilesAsync(object profilesPayload)
    {
        var response = await _client.PostAsJsonAsync(
            "/api/profiles/sync", profilesPayload, JsonOptions);
        response.EnsureSuccessStatusCode();
        return await response.Content.ReadFromJsonAsync<JsonElement>(JsonOptions);
    }
}
