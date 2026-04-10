using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using NewsSearcher.Api.Tests.Helpers;

namespace NewsSearcher.Api.Tests.Controllers;

public class BriefingControllerTests : IClassFixture<TestFactory>
{
    private readonly HttpClient _client;
    private readonly TestFactory _factory;

    public BriefingControllerTests(TestFactory factory)
    {
        _factory = factory;
        _client = factory.CreateClient();

        // Register default ML service responses
        _factory.MlHandler.RegisterOk("POST", "/api/briefing/generate",
            """{"id":"b0000000-0000-0000-0000-000000000001","user_id":"u001","status":"complete","article_count":2,"executive_summary":"Key items today...","articles":[]}""");
        _factory.MlHandler.RegisterOk("GET", "/api/briefing/latest",
            """{"id":"b0000000-0000-0000-0000-000000000001","user_id":"u001","status":"complete","article_count":2,"executive_summary":"Key items today...","articles":[]}""");
        _factory.MlHandler.RegisterOk("GET", "/api/briefing/history",
            """[{"id":"b0000000-0000-0000-0000-000000000001","status":"complete","article_count":2,"has_summary":true}]""");
        _factory.MlHandler.RegisterOk("GET", "/api/briefing/b0000000",
            """{"id":"b0000000-0000-0000-0000-000000000001","user_id":"u001","status":"complete","article_count":2,"executive_summary":"Key items today...","articles":[]}""");
    }

    private async Task<string> RegisterAndGetToken(string email = "briefing@example.com")
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
    public async Task Generate_Authenticated_ReturnsOk()
    {
        var token = await RegisterAndGetToken("briefing-gen@example.com");
        SetAuth(token);

        var response = await _client.PostAsync("/api/briefing/generate", null);

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        var body = await response.Content.ReadAsStringAsync();
        Assert.Contains("complete", body);
    }

    [Fact]
    public async Task Generate_Unauthenticated_ReturnsUnauthorized()
    {
        _client.DefaultRequestHeaders.Authorization = null;
        var response = await _client.PostAsync("/api/briefing/generate", null);
        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
    }

    [Fact]
    public async Task GetLatest_Authenticated_ReturnsOk()
    {
        var token = await RegisterAndGetToken("briefing-latest@example.com");
        SetAuth(token);

        var response = await _client.GetAsync("/api/briefing/latest");

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        var body = await response.Content.ReadAsStringAsync();
        Assert.Contains("executive_summary", body);
    }

    [Fact]
    public async Task GetHistory_Authenticated_ReturnsArray()
    {
        var token = await RegisterAndGetToken("briefing-hist@example.com");
        SetAuth(token);

        var response = await _client.GetAsync("/api/briefing/history");

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        var body = await response.Content.ReadAsStringAsync();
        Assert.Contains("article_count", body);
    }

    [Fact]
    public async Task GetById_Authenticated_ReturnsOk()
    {
        var token = await RegisterAndGetToken("briefing-byid@example.com");
        SetAuth(token);

        var response = await _client.GetAsync("/api/briefing/b0000000-0000-0000-0000-000000000001");

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        var body = await response.Content.ReadAsStringAsync();
        Assert.Contains("complete", body);
    }

    [Fact]
    public async Task GetLatest_Unauthenticated_ReturnsUnauthorized()
    {
        _client.DefaultRequestHeaders.Authorization = null;
        var response = await _client.GetAsync("/api/briefing/latest");
        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
    }
}
