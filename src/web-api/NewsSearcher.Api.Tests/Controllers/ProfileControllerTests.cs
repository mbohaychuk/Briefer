using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using NewsSearcher.Api.Tests.Helpers;

namespace NewsSearcher.Api.Tests.Controllers;

public class ProfileControllerTests : IClassFixture<TestFactory>
{
    private readonly HttpClient _client;

    public ProfileControllerTests(TestFactory factory)
    {
        _client = factory.CreateClient();
    }

    private async Task<string> RegisterAndGetToken(string email = "profile@example.com")
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
    public async Task GetProfile_Authenticated_ReturnsEmptyProfile()
    {
        var token = await RegisterAndGetToken("getprofile@example.com");
        SetAuth(token);

        var response = await _client.GetAsync("/api/profile");

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        var body = await response.Content.ReadAsStringAsync();
        Assert.Contains("interests", body);
    }

    [Fact]
    public async Task GetProfile_Unauthenticated_ReturnsUnauthorized()
    {
        _client.DefaultRequestHeaders.Authorization = null;
        var response = await _client.GetAsync("/api/profile");
        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
    }

    [Fact]
    public async Task AddInterest_ReturnsCreatedInterest()
    {
        var token = await RegisterAndGetToken("addinterest@example.com");
        SetAuth(token);

        var response = await _client.PostAsJsonAsync("/api/profile/interests", new
        {
            Title = "Oil & Gas Policy",
            Description = "I work in environmental policy for Alberta's oil and gas sector."
        });

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        var body = await response.Content.ReadAsStringAsync();
        Assert.Contains("Oil & Gas Policy", body);
    }

    [Fact]
    public async Task AddInterest_IncrementsProfileVersion()
    {
        var token = await RegisterAndGetToken("version@example.com");
        SetAuth(token);

        await _client.PostAsJsonAsync("/api/profile/interests", new
        {
            Title = "First Interest",
            Description = "Description one."
        });

        var response = await _client.GetAsync("/api/profile");
        var body = await response.Content.ReadAsStringAsync();
        Assert.Contains("\"version\":2", body);
    }

    [Fact]
    public async Task UpdateInterest_ChangesDescription()
    {
        var token = await RegisterAndGetToken("update@example.com");
        SetAuth(token);

        var createResponse = await _client.PostAsJsonAsync("/api/profile/interests", new
        {
            Title = "Original",
            Description = "Original description."
        });
        var created = await createResponse.Content.ReadFromJsonAsync<Dictionary<string, object>>();
        var interestId = created!["id"].ToString();

        var updateResponse = await _client.PutAsJsonAsync($"/api/profile/interests/{interestId}", new
        {
            Title = "Updated",
            Description = "Updated description."
        });

        Assert.Equal(HttpStatusCode.OK, updateResponse.StatusCode);
        var body = await updateResponse.Content.ReadAsStringAsync();
        Assert.Contains("Updated", body);
    }

    [Fact]
    public async Task DeleteInterest_RemovesFromProfile()
    {
        var token = await RegisterAndGetToken("delete@example.com");
        SetAuth(token);

        var createResponse = await _client.PostAsJsonAsync("/api/profile/interests", new
        {
            Title = "ToDelete",
            Description = "Will be deleted."
        });
        var created = await createResponse.Content.ReadFromJsonAsync<Dictionary<string, object>>();
        var interestId = created!["id"].ToString();

        var deleteResponse = await _client.DeleteAsync($"/api/profile/interests/{interestId}");
        Assert.Equal(HttpStatusCode.NoContent, deleteResponse.StatusCode);

        var profile = await _client.GetAsync("/api/profile");
        var body = await profile.Content.ReadAsStringAsync();
        Assert.DoesNotContain("ToDelete", body);
    }
}
