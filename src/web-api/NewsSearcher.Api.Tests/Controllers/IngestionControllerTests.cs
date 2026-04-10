using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using NewsSearcher.Api.Tests.Helpers;

namespace NewsSearcher.Api.Tests.Controllers;

public class IngestionControllerTests : IClassFixture<TestFactory>
{
    private readonly HttpClient _client;
    private readonly TestFactory _factory;

    public IngestionControllerTests(TestFactory factory)
    {
        _factory = factory;
        _client = factory.CreateClient();

        _factory.MlHandler.RegisterOk("POST", "/api/ingestion/trigger",
            """{"status":"completed","result":{"feeds_processed":3,"articles_new":12,"articles_duplicate":5}}""");
        _factory.MlHandler.RegisterOk("GET", "/api/ingestion/status",
            """{"running":false,"last_result":null,"last_run_at":null}""");
        _factory.MlHandler.RegisterOk("GET", "/api/ingestion/feeds",
            """{"feeds":[{"name":"CBC","url":"https://rss.cbc.ca/lineup/topstories.xml"}]}""");
    }

    private async Task<string> RegisterAndGetToken(string email = "ingestion@example.com")
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
        var token = await RegisterAndGetToken("ingestion-trigger@example.com");
        SetAuth(token);

        var response = await _client.PostAsync("/api/ingestion/trigger", null);

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        var body = await response.Content.ReadAsStringAsync();
        Assert.Contains("completed", body);
    }

    [Fact]
    public async Task Trigger_Unauthenticated_ReturnsUnauthorized()
    {
        _client.DefaultRequestHeaders.Authorization = null;
        var response = await _client.PostAsync("/api/ingestion/trigger", null);
        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
    }

    [Fact]
    public async Task GetStatus_Authenticated_ReturnsOk()
    {
        var token = await RegisterAndGetToken("ingestion-status@example.com");
        SetAuth(token);

        var response = await _client.GetAsync("/api/ingestion/status");

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        var body = await response.Content.ReadAsStringAsync();
        Assert.Contains("running", body);
    }

    [Fact]
    public async Task GetFeeds_Authenticated_ReturnsOk()
    {
        var token = await RegisterAndGetToken("ingestion-feeds@example.com");
        SetAuth(token);

        var response = await _client.GetAsync("/api/ingestion/feeds");

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        var body = await response.Content.ReadAsStringAsync();
        Assert.Contains("CBC", body);
    }

    [Fact]
    public async Task GetStatus_Unauthenticated_ReturnsUnauthorized()
    {
        _client.DefaultRequestHeaders.Authorization = null;
        var response = await _client.GetAsync("/api/ingestion/status");
        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
    }
}
