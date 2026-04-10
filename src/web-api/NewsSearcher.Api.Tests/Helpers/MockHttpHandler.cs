using System.Net;
using System.Text;

namespace NewsSearcher.Api.Tests.Helpers;

/// <summary>
/// A fake HttpMessageHandler that returns canned JSON responses keyed
/// by HTTP method + path prefix. Used to test controllers that proxy
/// requests through MlServiceClient without a live ML service.
/// </summary>
public class MockHttpHandler : HttpMessageHandler
{
    private readonly Dictionary<string, (HttpStatusCode Status, string Body)> _responses = new();

    /// <summary>
    /// Register a canned response. The key is "METHOD /path" (e.g. "POST /api/ingestion/trigger").
    /// Path matching is prefix-based so query strings are handled automatically.
    /// </summary>
    public void Register(string method, string pathPrefix, HttpStatusCode status, string jsonBody)
    {
        _responses[$"{method.ToUpperInvariant()} {pathPrefix}"] = (status, jsonBody);
    }

    /// <summary>Shorthand to register a 200 OK response.</summary>
    public void RegisterOk(string method, string pathPrefix, string jsonBody)
        => Register(method, pathPrefix, HttpStatusCode.OK, jsonBody);

    protected override Task<HttpResponseMessage> SendAsync(
        HttpRequestMessage request, CancellationToken cancellationToken)
    {
        var method = request.Method.Method.ToUpperInvariant();
        var path = request.RequestUri?.PathAndQuery ?? "";

        foreach (var (key, (status, body)) in _responses)
        {
            var parts = key.Split(' ', 2);
            if (parts[0] == method && path.StartsWith(parts[1], StringComparison.OrdinalIgnoreCase))
            {
                return Task.FromResult(new HttpResponseMessage(status)
                {
                    Content = new StringContent(body, Encoding.UTF8, "application/json"),
                });
            }
        }

        // No match → return 502 so tests fail loudly
        return Task.FromResult(new HttpResponseMessage(HttpStatusCode.BadGateway)
        {
            Content = new StringContent(
                """{"error":"MockHttpHandler: no response registered for this request"}""",
                Encoding.UTF8, "application/json"),
        });
    }
}
