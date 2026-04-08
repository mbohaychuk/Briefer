namespace NewsSearcher.Api.Models.Entities;

public class InterestDescription
{
    public Guid Id { get; set; } = Guid.NewGuid();
    public Guid UserProfileId { get; set; }
    public string Title { get; set; } = null!;
    public string Description { get; set; } = null!;
    public int SortOrder { get; set; }

    public UserProfile UserProfile { get; set; } = null!;
}
