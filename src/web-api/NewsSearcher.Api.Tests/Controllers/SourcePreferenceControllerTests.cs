using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using NewsSearcher.Api.Tests.Helpers;

namespace NewsSearcher.Api.Tests.Controllers;

public class SourcePreferenceControllerTests : IClassFixture<TestFactory>
{
    private readonly HttpClient _client;

    public SourcePreferenceControllerTests(TestFactory factory)
    {
        _client = factory.CreateClient();
    }

    private async Task<string> RegisterAndGetToken(string email)
    {
        var response = await _client.PostAsJsonAsync("/api/auth/register", new
        {
            Email = email,
            Password = "TestPass123"
        });
        var body = await response.Content.ReadFromJsonAsync<Dictionary<string, string>>();
        return body!["token"];
    }

    private void SetAuth(string token)
    {
        _client.DefaultRequestHeaders.Authorization =
            new AuthenticationHeaderValue("Bearer", token);
    }

    [Fact]
    public async Task GetPreferences_ReturnsSystemDefaults()
    {
        var token = await RegisterAndGetToken("prefs1@example.com");
        SetAuth(token);

        var response = await _client.GetAsync("/api/sourcepreferences");

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        var body = await response.Content.ReadAsStringAsync();
        Assert.Contains("theonion.com", body);
    }

    [Fact]
    public async Task AddBlocklistEntry_ReturnsCreated()
    {
        var token = await RegisterAndGetToken("prefs2@example.com");
        SetAuth(token);

        var response = await _client.PostAsJsonAsync("/api/sourcepreferences", new
        {
            Type = "Blocklist",
            Target = "unreliablenews.com"
        });

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        var body = await response.Content.ReadAsStringAsync();
        Assert.Contains("unreliablenews.com", body);
    }

    [Fact]
    public async Task AddPriorityEntry_ReturnsCreated()
    {
        var token = await RegisterAndGetToken("prefs3@example.com");
        SetAuth(token);

        var response = await _client.PostAsJsonAsync("/api/sourcepreferences", new
        {
            Type = "Priority",
            Target = "reuters.com"
        });

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        var body = await response.Content.ReadAsStringAsync();
        Assert.Contains("reuters.com", body);
    }

    [Fact]
    public async Task DeletePreference_RemovesEntry()
    {
        var token = await RegisterAndGetToken("prefs4@example.com");
        SetAuth(token);

        var createResponse = await _client.PostAsJsonAsync("/api/sourcepreferences", new
        {
            Type = "Blocklist",
            Target = "todelete.com"
        });
        var created = await createResponse.Content.ReadFromJsonAsync<Dictionary<string, object>>();
        var prefId = created!["id"].ToString();

        var deleteResponse = await _client.DeleteAsync($"/api/sourcepreferences/{prefId}");
        Assert.Equal(HttpStatusCode.NoContent, deleteResponse.StatusCode);
    }
}
