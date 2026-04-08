namespace NewsSearcher.Api.Models.DTOs.Profile;

public class ProfileResponse
{
    public int Version { get; set; }
    public List<InterestDescriptionDto> Interests { get; set; } = [];
}
