using System.Net;
using System.Net.Http.Json;
using NewsSearcher.Api.Tests.Helpers;

namespace NewsSearcher.Api.Tests.Controllers;

public class AuthControllerTests : IClassFixture<TestFactory>
{
    private readonly HttpClient _client;

    public AuthControllerTests(TestFactory factory)
    {
        _client = factory.CreateClient();
    }

    [Fact]
    public async Task Register_WithValidData_ReturnsToken()
    {
        var response = await _client.PostAsJsonAsync("/api/auth/register", new
        {
            Email = "test@example.com",
            Password = "TestPass123"
        });

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        var body = await response.Content.ReadFromJsonAsync<Dictionary<string, string>>();
        Assert.NotNull(body);
        Assert.True(body!.ContainsKey("token"));
        Assert.NotEmpty(body["token"]);
    }

    [Fact]
    public async Task Register_WithDuplicateEmail_ReturnsConflict()
    {
        await _client.PostAsJsonAsync("/api/auth/register", new
        {
            Email = "dupe@example.com",
            Password = "TestPass123"
        });

        var response = await _client.PostAsJsonAsync("/api/auth/register", new
        {
            Email = "dupe@example.com",
            Password = "TestPass123"
        });

        Assert.Equal(HttpStatusCode.Conflict, response.StatusCode);
    }

    [Fact]
    public async Task Login_WithValidCredentials_ReturnsToken()
    {
        await _client.PostAsJsonAsync("/api/auth/register", new
        {
            Email = "login@example.com",
            Password = "TestPass123"
        });

        var response = await _client.PostAsJsonAsync("/api/auth/login", new
        {
            Email = "login@example.com",
            Password = "TestPass123"
        });

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        var body = await response.Content.ReadFromJsonAsync<Dictionary<string, string>>();
        Assert.NotNull(body);
        Assert.True(body!.ContainsKey("token"));
    }

    [Fact]
    public async Task Login_WithWrongPassword_ReturnsUnauthorized()
    {
        await _client.PostAsJsonAsync("/api/auth/register", new
        {
            Email = "wrong@example.com",
            Password = "TestPass123"
        });

        var response = await _client.PostAsJsonAsync("/api/auth/login", new
        {
            Email = "wrong@example.com",
            Password = "WrongPass123"
        });

        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
    }
}
