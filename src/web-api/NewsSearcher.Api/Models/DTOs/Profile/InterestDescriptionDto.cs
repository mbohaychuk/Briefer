namespace NewsSearcher.Api.Models.DTOs.Profile;

public class InterestDescriptionDto
{
    public Guid Id { get; set; }
    public string Title { get; set; } = null!;
    public string Description { get; set; } = null!;
    public int SortOrder { get; set; }
}
