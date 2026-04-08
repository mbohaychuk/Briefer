namespace NewsSearcher.Api.Services;

public class MlServiceClient
{
    private readonly HttpClient _client;

    public MlServiceClient(IHttpClientFactory clientFactory)
    {
        _client = clientFactory.CreateClient("MlService");
    }

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
}
