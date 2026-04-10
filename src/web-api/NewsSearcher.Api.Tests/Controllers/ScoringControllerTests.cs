using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using NewsSearcher.Api.Tests.Helpers;

namespace NewsSearcher.Api.Tests.Controllers;

public class ScoringControllerTests : IClassFixture<TestFactory>
{
    private readonly HttpClient _client;
    private readonly TestFactory _factory;

    public ScoringControllerTests(TestFactory factory)
    {
        _factory = factory;
        _client = factory.CreateClient();

        _factory.MlHandler.RegisterOk("POST", "/api/scoring/trigger",
            """{"status":"completed","results":[{"user_id":"u001","candidates_retrieved":50,"stored":12}]}""");
        _factory.MlHandler.RegisterOk("GET", "/api/scoring/status",
            """{"running":false,"last_results":null,"last_run_at":null}""");
    }

    private async Task<string> RegisterAndGetToken(string email = "scoring@example.com")
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
    public async Task Trigger_Authenticated_ReturnsOk()
    {
        var token = await RegisterAndGetToken("scoring-trigger@example.com");
        SetAuth(token);

        var response = await _client.PostAsync("/api/scoring/trigger", null);

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        var body = await response.Content.ReadAsStringAsync();
        Assert.Contains("completed", body);
    }

    [Fact]
    public async Task Trigger_Unauthenticated_ReturnsUnauthorized()
    {
        _client.DefaultRequestHeaders.Authorization = null;
        var response = await _client.PostAsync("/api/scoring/trigger", null);
        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
    }

    [Fact]
    public async Task GetStatus_Authenticated_ReturnsOk()
    {
        var token = await RegisterAndGetToken("scoring-status@example.com");
        SetAuth(token);

        var response = await _client.GetAsync("/api/scoring/status");

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        var body = await response.Content.ReadAsStringAsync();
        Assert.Contains("running", body);
    }

    [Fact]
    public async Task GetStatus_Unauthenticated_ReturnsUnauthorized()
    {
        _client.DefaultRequestHeaders.Authorization = null;
        var response = await _client.GetAsync("/api/scoring/status");
        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
    }
}
