# Plan 1: Infrastructure & Core API — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the foundational infrastructure (Docker, PostgreSQL, Qdrant) and the ASP.NET Web API with authentication, user profile management, interest descriptions, and source preferences — plus a Python ML service skeleton that ASP.NET can communicate with.

**Architecture:** Two backend services (ASP.NET Web API + Python FastAPI) communicating via internal HTTP, sharing a PostgreSQL database. Qdrant runs alongside as a Docker container. ASP.NET handles all user-facing concerns; Python service exposes internal endpoints only. Auth uses ASP.NET Identity with JWT tokens.

**Tech Stack:** ASP.NET 8 (C#), Entity Framework Core, ASP.NET Identity, PostgreSQL, Python 3.12+, FastAPI, Qdrant, Docker Compose

---

## File Structure

```
news-searcher/
├── docker-compose.yml                          # PostgreSQL, Qdrant, web-api, ml-service
├── .env.example                                # Environment variable template
├── src/
│   ├── web-api/
│   │   ├── NewsSearcher.Api/
│   │   │   ├── NewsSearcher.Api.csproj
│   │   │   ├── Program.cs                      # Service configuration, middleware, auth
│   │   │   ├── appsettings.json
│   │   │   ├── appsettings.Development.json
│   │   │   ├── Controllers/
│   │   │   │   ├── AuthController.cs           # Register, login, refresh
│   │   │   │   ├── ProfileController.cs        # Interest description CRUD
│   │   │   │   └── SourcePreferenceController.cs # Blocklist/priority CRUD
│   │   │   ├── Models/
│   │   │   │   ├── Entities/
│   │   │   │   │   ├── ApplicationUser.cs      # Extends IdentityUser
│   │   │   │   │   ├── UserProfile.cs          # Versioned interest profile
│   │   │   │   │   ├── InterestDescription.cs  # Individual interest block
│   │   │   │   │   └── SourcePreference.cs     # Blocklist/priority entry
│   │   │   │   └── DTOs/
│   │   │   │       ├── Auth/
│   │   │   │       │   ├── RegisterRequest.cs
│   │   │   │       │   ├── LoginRequest.cs
│   │   │   │       │   └── AuthResponse.cs
│   │   │   │       ├── Profile/
│   │   │   │       │   ├── InterestDescriptionDto.cs
│   │   │   │       │   ├── CreateInterestRequest.cs
│   │   │   │       │   ├── UpdateInterestRequest.cs
│   │   │   │       │   └── ProfileResponse.cs
│   │   │   │       └── SourcePreference/
│   │   │   │           ├── SourcePreferenceDto.cs
│   │   │   │           ├── CreateSourcePreferenceRequest.cs
│   │   │   │           └── SourcePreferenceResponse.cs
│   │   │   ├── Data/
│   │   │   │   └── AppDbContext.cs             # EF Core context
│   │   │   └── Services/
│   │   │       ├── TokenService.cs             # JWT generation
│   │   │       └── MlServiceClient.cs          # HTTP client to Python service
│   │   └── NewsSearcher.Api.Tests/
│   │       ├── NewsSearcher.Api.Tests.csproj
│   │       ├── Controllers/
│   │       │   ├── AuthControllerTests.cs
│   │       │   ├── ProfileControllerTests.cs
│   │       │   └── SourcePreferenceControllerTests.cs
│   │       └── Helpers/
│   │           └── TestFactory.cs              # WebApplicationFactory setup
│   │
│   └── ml-service/
│       ├── requirements.txt
│       ├── app/
│       │   ├── __init__.py
│       │   ├── main.py                         # FastAPI app entry point
│       │   └── routers/
│       │       ├── __init__.py
│       │       └── health.py                   # Health check endpoint
│       └── tests/
│           ├── __init__.py
│           └── test_health.py
```

---

## Task 1: Docker Compose & Environment

**Files:**
- Create: `docker-compose.yml`
- Create: `.env.example`
- Create: `.gitignore`

- [ ] **Step 1: Create .gitignore**

```gitignore
# .NET
bin/
obj/
*.user
*.suo
appsettings.Development.json

# Python
__pycache__/
*.pyc
.venv/
*.egg-info/

# Environment
.env

# IDE
.vs/
.vscode/
.idea/

# OS
Thumbs.db
.DS_Store
```

- [ ] **Step 2: Create .env.example**

```env
# PostgreSQL
POSTGRES_USER=newssearcher
POSTGRES_PASSWORD=changeme_dev
POSTGRES_DB=newssearcher

# Qdrant
QDRANT_HOST=qdrant
QDRANT_PORT=6333

# JWT
JWT_SECRET=changeme_dev_secret_at_least_32_chars_long
JWT_ISSUER=NewsSearcher
JWT_AUDIENCE=NewsSearcher

# ML Service
ML_SERVICE_URL=http://ml-service:8000
ML_SERVICE_API_KEY=changeme_dev_ml_api_key
```

- [ ] **Step 3: Create docker-compose.yml**

```yaml
services:
  postgres:
    image: postgres:16
    env_file: .env
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $POSTGRES_USER"]
      interval: 5s
      timeout: 5s
      retries: 5

  qdrant:
    image: qdrant/qdrant:v1.13.2
    ports:
      - "6333:6333"
      - "6334:6334"
    volumes:
      - qdrant_data:/qdrant/storage
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6333/healthz"]
      interval: 5s
      timeout: 5s
      retries: 5

  web-api:
    build:
      context: ./src/web-api
      dockerfile: Dockerfile
    ports:
      - "5000:8080"
    env_file: .env
    environment:
      - ConnectionStrings__DefaultConnection=Host=postgres;Database=${POSTGRES_DB};Username=${POSTGRES_USER};Password=${POSTGRES_PASSWORD}
      - MlService__BaseUrl=http://ml-service:8000
      - MlService__ApiKey=${ML_SERVICE_API_KEY}
    depends_on:
      postgres:
        condition: service_healthy

  ml-service:
    build:
      context: ./src/ml-service
      dockerfile: Dockerfile
    env_file: .env
    environment:
      - QDRANT_HOST=qdrant
      - QDRANT_PORT=6333
      - DATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
      - ML_SERVICE_API_KEY=${ML_SERVICE_API_KEY}
    depends_on:
      postgres:
        condition: service_healthy
      qdrant:
        condition: service_healthy

volumes:
  postgres_data:
  qdrant_data:
```

- [ ] **Step 4: Create docker-compose.dev.yml**

This override exposes debug ports and enables hot reload for development. The ml-service port is only exposed here, not in the production compose.

```yaml
# docker-compose.dev.yml — development overrides
services:
  web-api:
    ports:
      - "5000:8080"
      - "5001:5001"  # Debug port

  ml-service:
    ports:
      - "8000:8000"  # Only exposed in dev
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

- [ ] **Step 5: Copy .env.example to .env**

Run: `cp .env.example .env`

- [ ] **Step 6: Start infrastructure services only to verify**

Run: `docker compose up postgres qdrant -d`
Expected: Both services healthy. Verify with `docker compose ps` — both should show "healthy".

- [ ] **Step 7: Stop services and commit**

Run: `docker compose down`

```bash
git init
git add .gitignore .env.example docker-compose.yml docker-compose.dev.yml
git commit -m "chore: add docker compose with postgres and qdrant"
```

---

## Task 2: ASP.NET Project Scaffolding

**Files:**
- Create: `src/web-api/NewsSearcher.Api/NewsSearcher.Api.csproj`
- Create: `src/web-api/NewsSearcher.Api/Program.cs`
- Create: `src/web-api/NewsSearcher.Api/appsettings.json`
- Create: `src/web-api/Dockerfile`
- Create: `src/web-api/NewsSearcher.Api.Tests/NewsSearcher.Api.Tests.csproj`

- [ ] **Step 1: Create the ASP.NET Web API project**

Run from repo root:
```bash
mkdir -p src/web-api
cd src/web-api
dotnet new webapi -n NewsSearcher.Api --no-openapi
dotnet new xunit -n NewsSearcher.Api.Tests
dotnet add NewsSearcher.Api.Tests/NewsSearcher.Api.Tests.csproj reference NewsSearcher.Api/NewsSearcher.Api.csproj
```

- [ ] **Step 2: Add NuGet packages**

Run from `src/web-api/NewsSearcher.Api/`:
```bash
dotnet add package Npgsql.EntityFrameworkCore.PostgreSQL
dotnet add package Microsoft.AspNetCore.Identity.EntityFrameworkCore
dotnet add package Microsoft.AspNetCore.Authentication.JwtBearer
dotnet add package EFCore.NamingConventions
dotnet add package Microsoft.Extensions.Http.Resilience
```

Run from `src/web-api/NewsSearcher.Api.Tests/`:
```bash
dotnet add package Microsoft.AspNetCore.Mvc.Testing
dotnet add package Microsoft.EntityFrameworkCore.InMemory
```

- [ ] **Step 3: Replace appsettings.json**

Replace `src/web-api/NewsSearcher.Api/appsettings.json`:

```json
{
  "Logging": {
    "LogLevel": {
      "Default": "Information",
      "Microsoft.AspNetCore": "Warning"
    }
  },
  "ConnectionStrings": {
    "DefaultConnection": "Host=localhost;Database=newssearcher;Username=newssearcher;Password=changeme_dev"
  },
  "Jwt": {
    "Secret": "changeme_dev_secret_at_least_32_chars_long",
    "Issuer": "NewsSearcher",
    "Audience": "NewsSearcher",
    "ExpiryMinutes": 60
  },
  "MlService": {
    "BaseUrl": "http://localhost:8000",
    "ApiKey": "changeme_dev_ml_api_key"
  }
}
```

- [ ] **Step 4: Create Dockerfile for web-api**

Create `src/web-api/Dockerfile`:

```dockerfile
FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src
COPY NewsSearcher.Api/NewsSearcher.Api.csproj NewsSearcher.Api/
RUN dotnet restore NewsSearcher.Api/NewsSearcher.Api.csproj
COPY NewsSearcher.Api/ NewsSearcher.Api/
RUN dotnet publish NewsSearcher.Api/NewsSearcher.Api.csproj -c Release -o /app

FROM mcr.microsoft.com/dotnet/aspnet:8.0
WORKDIR /app
COPY --from=build /app .
EXPOSE 8080
ENTRYPOINT ["dotnet", "NewsSearcher.Api.dll"]
```

- [ ] **Step 5: Verify project builds**

Run from `src/web-api/`:
```bash
dotnet build
```
Expected: Build succeeded with 0 errors.

- [ ] **Step 6: Commit**

```bash
git add src/web-api/
git commit -m "chore: scaffold asp.net web api project with test project"
```

---

## Task 3: Database Context & Entity Models

**Files:**
- Create: `src/web-api/NewsSearcher.Api/Models/Entities/ApplicationUser.cs`
- Create: `src/web-api/NewsSearcher.Api/Models/Entities/UserProfile.cs`
- Create: `src/web-api/NewsSearcher.Api/Models/Entities/InterestDescription.cs`
- Create: `src/web-api/NewsSearcher.Api/Models/Entities/SourcePreference.cs`
- Create: `src/web-api/NewsSearcher.Api/Data/AppDbContext.cs`

- [ ] **Step 1: Create ApplicationUser entity**

Create `src/web-api/NewsSearcher.Api/Models/Entities/ApplicationUser.cs`:

```csharp
using Microsoft.AspNetCore.Identity;

namespace NewsSearcher.Api.Models.Entities;

public class ApplicationUser : IdentityUser
{
    public int CurrentProfileVersion { get; set; } = 1;
    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;

    public ICollection<UserProfile> Profiles { get; set; } = [];
    public ICollection<SourcePreference> SourcePreferences { get; set; } = [];
}
```

- [ ] **Step 2: Create UserProfile entity**

Create `src/web-api/NewsSearcher.Api/Models/Entities/UserProfile.cs`:

```csharp
namespace NewsSearcher.Api.Models.Entities;

public class UserProfile
{
    public Guid Id { get; set; } = Guid.NewGuid();
    public string UserId { get; set; } = null!;
    public int Version { get; set; }
    public bool IsCurrent { get; set; } = true;
    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;

    public ApplicationUser User { get; set; } = null!;
    public ICollection<InterestDescription> Interests { get; set; } = [];
}
```

- [ ] **Step 3: Create InterestDescription entity**

Create `src/web-api/NewsSearcher.Api/Models/Entities/InterestDescription.cs`:

```csharp
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
```

- [ ] **Step 4: Create SourcePreference entity**

Create `src/web-api/NewsSearcher.Api/Models/Entities/SourcePreference.cs`:

```csharp
namespace NewsSearcher.Api.Models.Entities;

public enum PreferenceType
{
    Blocklist,
    Priority
}

public class SourcePreference
{
    public Guid Id { get; set; } = Guid.NewGuid();
    public string? UserId { get; set; }
    public PreferenceType Type { get; set; }
    public string Target { get; set; } = null!;
    public bool IsSystemDefault { get; set; }
    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;

    public ApplicationUser? User { get; set; }
}
```

- [ ] **Step 5: Create AppDbContext**

Create `src/web-api/NewsSearcher.Api/Data/AppDbContext.cs`:

```csharp
using Microsoft.AspNetCore.Identity.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore;
using NewsSearcher.Api.Models.Entities;

namespace NewsSearcher.Api.Data;

public class AppDbContext : IdentityDbContext<ApplicationUser>
{
    public AppDbContext(DbContextOptions<AppDbContext> options) : base(options) { }

    public DbSet<UserProfile> UserProfiles => Set<UserProfile>();
    public DbSet<InterestDescription> InterestDescriptions => Set<InterestDescription>();
    public DbSet<SourcePreference> SourcePreferences => Set<SourcePreference>();

    protected override void OnModelCreating(ModelBuilder builder)
    {
        base.OnModelCreating(builder);

        builder.Entity<UserProfile>(e =>
        {
            e.HasIndex(p => new { p.UserId, p.Version }).IsUnique();
            e.HasIndex(p => new { p.UserId, p.IsCurrent })
                .HasFilter("is_current = true")
                .IsUnique();
        });

        builder.Entity<InterestDescription>(e =>
        {
            e.HasIndex(i => new { i.UserProfileId, i.SortOrder });
        });

        builder.Entity<SourcePreference>(e =>
        {
            e.HasIndex(s => new { s.UserId, s.Type, s.Target }).IsUnique();
        });
    }
}
```

- [ ] **Step 6: Verify build**

Run from `src/web-api/`:
```bash
dotnet build
```
Expected: Build succeeded.

- [ ] **Step 7: Commit**

```bash
git add src/web-api/NewsSearcher.Api/Models/ src/web-api/NewsSearcher.Api/Data/
git commit -m "feat: add entity models and db context for users, profiles, interests, source preferences"
```

---

## Task 4: Program.cs — Service Configuration & Auth

**Files:**
- Modify: `src/web-api/NewsSearcher.Api/Program.cs`
- Create: `src/web-api/NewsSearcher.Api/Services/TokenService.cs`

- [ ] **Step 1: Create TokenService**

Create `src/web-api/NewsSearcher.Api/Services/TokenService.cs`:

```csharp
using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using System.Text;
using Microsoft.IdentityModel.Tokens;
using NewsSearcher.Api.Models.Entities;

namespace NewsSearcher.Api.Services;

public class TokenService
{
    private readonly IConfiguration _config;

    public TokenService(IConfiguration config)
    {
        _config = config;
    }

    public string GenerateToken(ApplicationUser user)
    {
        var claims = new List<Claim>
        {
            new(ClaimTypes.NameIdentifier, user.Id),
            new(ClaimTypes.Email, user.Email!),
        };

        var key = new SymmetricSecurityKey(
            Encoding.UTF8.GetBytes(_config["Jwt:Secret"]!));
        var creds = new SigningCredentials(key, SecurityAlgorithms.HmacSha256);

        var token = new JwtSecurityToken(
            issuer: _config["Jwt:Issuer"],
            audience: _config["Jwt:Audience"],
            claims: claims,
            expires: DateTime.UtcNow.AddMinutes(
                int.Parse(_config["Jwt:ExpiryMinutes"] ?? "60")),
            signingCredentials: creds
        );

        return new JwtSecurityTokenHandler().WriteToken(token);
    }
}
```

- [ ] **Step 2: Replace Program.cs**

Replace `src/web-api/NewsSearcher.Api/Program.cs`:

```csharp
using System.Text;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.AspNetCore.Identity;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Http.Resilience;
using Microsoft.IdentityModel.Tokens;
using NewsSearcher.Api.Data;
using NewsSearcher.Api.Models.Entities;
using NewsSearcher.Api.Services;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddControllers();

builder.Services.AddDbContext<AppDbContext>(options =>
    options.UseNpgsql(builder.Configuration.GetConnectionString("DefaultConnection"))
           .UseSnakeCaseNamingConvention());

builder.Services.AddIdentityCore<ApplicationUser>(options =>
    {
        options.Password.RequireDigit = true;
        options.Password.RequiredLength = 8;
        options.Password.RequireNonAlphanumeric = false;
        options.User.RequireUniqueEmail = true;
    })
    .AddEntityFrameworkStores<AppDbContext>()
    .AddDefaultTokenProviders();

builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
    .AddJwtBearer(options =>
    {
        options.TokenValidationParameters = new TokenValidationParameters
        {
            ValidateIssuer = true,
            ValidateAudience = true,
            ValidateLifetime = true,
            ValidateIssuerSigningKey = true,
            ValidIssuer = builder.Configuration["Jwt:Issuer"],
            ValidAudience = builder.Configuration["Jwt:Audience"],
            IssuerSigningKey = new SymmetricSecurityKey(
                Encoding.UTF8.GetBytes(builder.Configuration["Jwt:Secret"]!))
        };
    });

builder.Services.AddAuthorization();
builder.Services.AddScoped<TokenService>();

builder.Services.AddHttpClient("MlService", client =>
{
    client.BaseAddress = new Uri(builder.Configuration["MlService:BaseUrl"]!);
    client.Timeout = TimeSpan.FromSeconds(60);
    client.DefaultRequestHeaders.Add("X-Api-Key", builder.Configuration["MlService:ApiKey"]!);
})
.AddStandardResilienceHandler(options =>
{
    options.Retry.MaxRetryAttempts = 3;
    options.Retry.Delay = TimeSpan.FromSeconds(2);
    options.CircuitBreaker.BreakDuration = TimeSpan.FromSeconds(30);
});

var app = builder.Build();

using (var scope = app.Services.CreateScope())
{
    var db = scope.ServiceProvider.GetRequiredService<AppDbContext>();
    db.Database.Migrate();
}

app.UseAuthentication();
app.UseAuthorization();
app.MapControllers();

app.Run();

public partial class Program { }
```

The `public partial class Program { }` line at the bottom allows the test project's `WebApplicationFactory` to reference the entry point.

- [ ] **Step 3: Generate initial migration**

Run from `src/web-api/`:
```bash
dotnet tool install --global dotnet-ef
dotnet ef migrations add InitialCreate --project NewsSearcher.Api
```
Expected: Migration files created in `NewsSearcher.Api/Migrations/`.

- [ ] **Step 4: Verify build**

Run: `dotnet build`
Expected: Build succeeded.

- [ ] **Step 5: Commit**

```bash
git add src/web-api/NewsSearcher.Api/
git commit -m "feat: configure asp.net identity, jwt auth, ef core with postgres"
```

---

## Task 5: Test Factory Setup

**Files:**
- Create: `src/web-api/NewsSearcher.Api.Tests/Helpers/TestFactory.cs`

- [ ] **Step 1: Create TestFactory**

This configures an in-memory database for integration tests so tests don't need a running PostgreSQL instance.

Create `src/web-api/NewsSearcher.Api.Tests/Helpers/TestFactory.cs`:

```csharp
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using NewsSearcher.Api.Data;

namespace NewsSearcher.Api.Tests.Helpers;

public class TestFactory : WebApplicationFactory<Program>
{
    protected override void ConfigureWebHost(IWebHostBuilder builder)
    {
        builder.ConfigureServices(services =>
        {
            var descriptor = services.SingleOrDefault(
                d => d.ServiceType == typeof(DbContextOptions<AppDbContext>));
            if (descriptor != null)
                services.Remove(descriptor);

            services.AddDbContext<AppDbContext>(options =>
                options.UseInMemoryDatabase("TestDb_" + Guid.NewGuid()));
        });

        builder.UseEnvironment("Testing");
    }
}
```

- [ ] **Step 2: Verify tests project builds**

Run from `src/web-api/`:
```bash
dotnet build NewsSearcher.Api.Tests/
```
Expected: Build succeeded.

- [ ] **Step 3: Commit**

```bash
git add src/web-api/NewsSearcher.Api.Tests/
git commit -m "feat: add test factory with in-memory database for integration tests"
```

---

## Task 6: Auth Controller (Register & Login)

**Files:**
- Create: `src/web-api/NewsSearcher.Api/Models/DTOs/Auth/RegisterRequest.cs`
- Create: `src/web-api/NewsSearcher.Api/Models/DTOs/Auth/LoginRequest.cs`
- Create: `src/web-api/NewsSearcher.Api/Models/DTOs/Auth/AuthResponse.cs`
- Create: `src/web-api/NewsSearcher.Api/Controllers/AuthController.cs`
- Create: `src/web-api/NewsSearcher.Api.Tests/Controllers/AuthControllerTests.cs`

- [ ] **Step 1: Write failing auth tests**

Create `src/web-api/NewsSearcher.Api.Tests/Controllers/AuthControllerTests.cs`:

```csharp
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `dotnet test src/web-api/NewsSearcher.Api.Tests/ --filter AuthControllerTests -v n`
Expected: All 4 tests FAIL (404 — no controller exists yet).

- [ ] **Step 3: Create auth DTOs**

Create `src/web-api/NewsSearcher.Api/Models/DTOs/Auth/RegisterRequest.cs`:

```csharp
using System.ComponentModel.DataAnnotations;

namespace NewsSearcher.Api.Models.DTOs.Auth;

public class RegisterRequest
{
    [Required, EmailAddress]
    public string Email { get; set; } = null!;

    [Required, MinLength(8)]
    public string Password { get; set; } = null!;
}
```

Create `src/web-api/NewsSearcher.Api/Models/DTOs/Auth/LoginRequest.cs`:

```csharp
using System.ComponentModel.DataAnnotations;

namespace NewsSearcher.Api.Models.DTOs.Auth;

public class LoginRequest
{
    [Required, EmailAddress]
    public string Email { get; set; } = null!;

    [Required]
    public string Password { get; set; } = null!;
}
```

Create `src/web-api/NewsSearcher.Api/Models/DTOs/Auth/AuthResponse.cs`:

```csharp
namespace NewsSearcher.Api.Models.DTOs.Auth;

public class AuthResponse
{
    public string Token { get; set; } = null!;
}
```

- [ ] **Step 4: Create AuthController**

Create `src/web-api/NewsSearcher.Api/Controllers/AuthController.cs`:

```csharp
using Microsoft.AspNetCore.Identity;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using NewsSearcher.Api.Data;
using NewsSearcher.Api.Models.DTOs.Auth;
using NewsSearcher.Api.Models.Entities;
using NewsSearcher.Api.Services;

namespace NewsSearcher.Api.Controllers;

[ApiController]
[Route("api/[controller]")]
public class AuthController : ControllerBase
{
    private readonly UserManager<ApplicationUser> _userManager;
    private readonly TokenService _tokenService;
    private readonly AppDbContext _db;

    public AuthController(
        UserManager<ApplicationUser> userManager,
        TokenService tokenService,
        AppDbContext db)
    {
        _userManager = userManager;
        _tokenService = tokenService;
        _db = db;
    }

    [HttpPost("register")]
    public async Task<IActionResult> Register(RegisterRequest request)
    {
        var existing = await _userManager.FindByEmailAsync(request.Email);
        if (existing != null)
            return Conflict(new { error = "Email already registered" });

        var user = new ApplicationUser
        {
            UserName = request.Email,
            Email = request.Email
        };

        var result = await _userManager.CreateAsync(user, request.Password);
        if (!result.Succeeded)
            return BadRequest(new { errors = result.Errors.Select(e => e.Description) });

        var profile = new UserProfile
        {
            UserId = user.Id,
            Version = 1,
            IsCurrent = true
        };
        _db.UserProfiles.Add(profile);
        await _db.SaveChangesAsync();

        var token = _tokenService.GenerateToken(user);
        return Ok(new AuthResponse { Token = token });
    }

    [HttpPost("login")]
    public async Task<IActionResult> Login(LoginRequest request)
    {
        var user = await _userManager.FindByEmailAsync(request.Email);
        if (user == null)
            return Unauthorized(new { error = "Invalid credentials" });

        var valid = await _userManager.CheckPasswordAsync(user, request.Password);
        if (!valid)
            return Unauthorized(new { error = "Invalid credentials" });

        var token = _tokenService.GenerateToken(user);
        return Ok(new AuthResponse { Token = token });
    }
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `dotnet test src/web-api/NewsSearcher.Api.Tests/ --filter AuthControllerTests -v n`
Expected: All 4 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/web-api/
git commit -m "feat: add auth controller with register and login endpoints"
```

---

## Task 7: Profile Controller (Interest Descriptions CRUD)

**Files:**
- Create: `src/web-api/NewsSearcher.Api/Models/DTOs/Profile/InterestDescriptionDto.cs`
- Create: `src/web-api/NewsSearcher.Api/Models/DTOs/Profile/CreateInterestRequest.cs`
- Create: `src/web-api/NewsSearcher.Api/Models/DTOs/Profile/UpdateInterestRequest.cs`
- Create: `src/web-api/NewsSearcher.Api/Models/DTOs/Profile/ProfileResponse.cs`
- Create: `src/web-api/NewsSearcher.Api/Controllers/ProfileController.cs`
- Create: `src/web-api/NewsSearcher.Api.Tests/Controllers/ProfileControllerTests.cs`

- [ ] **Step 1: Write failing profile tests**

Create `src/web-api/NewsSearcher.Api.Tests/Controllers/ProfileControllerTests.cs`:

```csharp
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `dotnet test src/web-api/NewsSearcher.Api.Tests/ --filter ProfileControllerTests -v n`
Expected: All tests FAIL (404 — no controller yet).

- [ ] **Step 3: Create profile DTOs**

Create `src/web-api/NewsSearcher.Api/Models/DTOs/Profile/InterestDescriptionDto.cs`:

```csharp
namespace NewsSearcher.Api.Models.DTOs.Profile;

public class InterestDescriptionDto
{
    public Guid Id { get; set; }
    public string Title { get; set; } = null!;
    public string Description { get; set; } = null!;
    public int SortOrder { get; set; }
}
```

Create `src/web-api/NewsSearcher.Api/Models/DTOs/Profile/CreateInterestRequest.cs`:

```csharp
using System.ComponentModel.DataAnnotations;

namespace NewsSearcher.Api.Models.DTOs.Profile;

public class CreateInterestRequest
{
    [Required, MaxLength(200)]
    public string Title { get; set; } = null!;

    [Required, MaxLength(5000)]
    public string Description { get; set; } = null!;
}
```

Create `src/web-api/NewsSearcher.Api/Models/DTOs/Profile/UpdateInterestRequest.cs`:

```csharp
using System.ComponentModel.DataAnnotations;

namespace NewsSearcher.Api.Models.DTOs.Profile;

public class UpdateInterestRequest
{
    [Required, MaxLength(200)]
    public string Title { get; set; } = null!;

    [Required, MaxLength(5000)]
    public string Description { get; set; } = null!;

    public int? SortOrder { get; set; }
}
```

Create `src/web-api/NewsSearcher.Api/Models/DTOs/Profile/ProfileResponse.cs`:

```csharp
namespace NewsSearcher.Api.Models.DTOs.Profile;

public class ProfileResponse
{
    public int Version { get; set; }
    public List<InterestDescriptionDto> Interests { get; set; } = [];
}
```

- [ ] **Step 4: Create ProfileController**

Create `src/web-api/NewsSearcher.Api/Controllers/ProfileController.cs`:

```csharp
using System.Security.Claims;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using NewsSearcher.Api.Data;
using NewsSearcher.Api.Models.DTOs.Profile;
using NewsSearcher.Api.Models.Entities;

namespace NewsSearcher.Api.Controllers;

[ApiController]
[Route("api/[controller]")]
[Authorize]
public class ProfileController : ControllerBase
{
    private readonly AppDbContext _db;

    public ProfileController(AppDbContext db)
    {
        _db = db;
    }

    private string UserId => User.FindFirstValue(ClaimTypes.NameIdentifier)!;

    [HttpGet]
    public async Task<IActionResult> GetProfile()
    {
        var profile = await _db.UserProfiles
            .Include(p => p.Interests.OrderBy(i => i.SortOrder))
            .FirstOrDefaultAsync(p => p.UserId == UserId && p.IsCurrent);

        if (profile == null)
            return NotFound();

        return Ok(new ProfileResponse
        {
            Version = profile.Version,
            Interests = profile.Interests.Select(i => new InterestDescriptionDto
            {
                Id = i.Id,
                Title = i.Title,
                Description = i.Description,
                SortOrder = i.SortOrder
            }).ToList()
        });
    }

    [HttpPost("interests")]
    public async Task<IActionResult> AddInterest(CreateInterestRequest request)
    {
        var newProfile = await CreateNewProfileVersion();

        var maxOrder = newProfile.Interests.Any()
            ? newProfile.Interests.Max(i => i.SortOrder)
            : -1;

        var interest = new InterestDescription
        {
            UserProfileId = newProfile.Id,
            Title = request.Title,
            Description = request.Description,
            SortOrder = maxOrder + 1
        };
        newProfile.Interests.Add(interest);
        await _db.SaveChangesAsync();

        return Ok(new InterestDescriptionDto
        {
            Id = interest.Id,
            Title = interest.Title,
            Description = interest.Description,
            SortOrder = interest.SortOrder
        });
    }

    [HttpPut("interests/{interestId:guid}")]
    public async Task<IActionResult> UpdateInterest(Guid interestId, UpdateInterestRequest request)
    {
        var newProfile = await CreateNewProfileVersion();

        // The client sends the old interest ID — translate via mapping
        var mappedId = ResolveInterestId(interestId);
        var interest = newProfile.Interests.FirstOrDefault(i => i.Id == mappedId);
        if (interest == null)
            return NotFound();

        interest.Title = request.Title;
        interest.Description = request.Description;
        if (request.SortOrder.HasValue)
            interest.SortOrder = request.SortOrder.Value;

        await _db.SaveChangesAsync();

        return Ok(new InterestDescriptionDto
        {
            Id = interest.Id,
            Title = interest.Title,
            Description = interest.Description,
            SortOrder = interest.SortOrder
        });
    }

    private Guid ResolveInterestId(Guid clientId)
    {
        if (HttpContext.Items["InterestIdMapping"] is Dictionary<Guid, Guid> mapping
            && mapping.TryGetValue(clientId, out var newId))
            return newId;
        return clientId;
    }

    [HttpDelete("interests/{interestId:guid}")]
    public async Task<IActionResult> DeleteInterest(Guid interestId)
    {
        var newProfile = await CreateNewProfileVersion();

        var mappedId = ResolveInterestId(interestId);
        var interest = newProfile.Interests.FirstOrDefault(i => i.Id == mappedId);
        if (interest == null)
            return NotFound();

        newProfile.Interests.Remove(interest);
        _db.InterestDescriptions.Remove(interest);
        await _db.SaveChangesAsync();

        return NoContent();
    }

    private async Task<UserProfile> CreateNewProfileVersion()
    {
        var currentProfile = await _db.UserProfiles
            .Include(p => p.Interests)
            .FirstAsync(p => p.UserId == UserId && p.IsCurrent);

        var user = await _db.Users.FindAsync(UserId);
        user!.CurrentProfileVersion++;

        currentProfile.IsCurrent = false;

        var newProfile = new UserProfile
        {
            UserId = UserId,
            Version = user.CurrentProfileVersion,
            IsCurrent = true
        };

        // Build a mapping from old interest IDs to new interest IDs
        // so that Update/Delete can find interests by the ID the client knows
        var idMapping = new Dictionary<Guid, Guid>();

        foreach (var interest in currentProfile.Interests)
        {
            var newInterest = new InterestDescription
            {
                // New GUID — do NOT reuse interest.Id (causes PK violation on real PostgreSQL)
                UserProfileId = newProfile.Id,
                Title = interest.Title,
                Description = interest.Description,
                SortOrder = interest.SortOrder
            };
            newProfile.Interests.Add(newInterest);
            idMapping[interest.Id] = newInterest.Id;
        }

        _db.UserProfiles.Add(newProfile);
        await _db.SaveChangesAsync();

        // Store mapping in HttpContext so Update/Delete can translate old IDs
        HttpContext.Items["InterestIdMapping"] = idMapping;

        return newProfile;
    }
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `dotnet test src/web-api/NewsSearcher.Api.Tests/ --filter ProfileControllerTests -v n`
Expected: All 6 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/web-api/
git commit -m "feat: add profile controller with interest description CRUD and versioning"
```

---

## Task 8: Source Preference Controller

**Files:**
- Create: `src/web-api/NewsSearcher.Api/Models/DTOs/SourcePreference/SourcePreferenceDto.cs`
- Create: `src/web-api/NewsSearcher.Api/Models/DTOs/SourcePreference/CreateSourcePreferenceRequest.cs`
- Create: `src/web-api/NewsSearcher.Api/Controllers/SourcePreferenceController.cs`
- Create: `src/web-api/NewsSearcher.Api.Tests/Controllers/SourcePreferenceControllerTests.cs`

- [ ] **Step 1: Write failing source preference tests**

Create `src/web-api/NewsSearcher.Api.Tests/Controllers/SourcePreferenceControllerTests.cs`:

```csharp
using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using NewsSearcher.Api.Tests.Helpers;

namespace NewsSearcher.Api.Tests.Controllers;

public class SourcePreferenceControllerTests : IClassFixture<TestFactory>
{
    private readonly HttpClient _client;

    public SourcePreferenceControllerTests(TestFactory factory)
    {
        _client = factory.CreateClient();
    }

    private async Task<string> RegisterAndGetToken(string email)
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
    public async Task GetPreferences_ReturnsSystemDefaults()
    {
        var token = await RegisterAndGetToken("prefs1@example.com");
        SetAuth(token);

        var response = await _client.GetAsync("/api/sourcepreferences");

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        var body = await response.Content.ReadAsStringAsync();
        Assert.Contains("theonion.com", body);
    }

    [Fact]
    public async Task AddBlocklistEntry_ReturnsCreated()
    {
        var token = await RegisterAndGetToken("prefs2@example.com");
        SetAuth(token);

        var response = await _client.PostAsJsonAsync("/api/sourcepreferences", new
        {
            Type = "Blocklist",
            Target = "unreliablenews.com"
        });

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        var body = await response.Content.ReadAsStringAsync();
        Assert.Contains("unreliablenews.com", body);
    }

    [Fact]
    public async Task AddPriorityEntry_ReturnsCreated()
    {
        var token = await RegisterAndGetToken("prefs3@example.com");
        SetAuth(token);

        var response = await _client.PostAsJsonAsync("/api/sourcepreferences", new
        {
            Type = "Priority",
            Target = "reuters.com"
        });

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        var body = await response.Content.ReadAsStringAsync();
        Assert.Contains("reuters.com", body);
    }

    [Fact]
    public async Task DeletePreference_RemovesEntry()
    {
        var token = await RegisterAndGetToken("prefs4@example.com");
        SetAuth(token);

        var createResponse = await _client.PostAsJsonAsync("/api/sourcepreferences", new
        {
            Type = "Blocklist",
            Target = "todelete.com"
        });
        var created = await createResponse.Content.ReadFromJsonAsync<Dictionary<string, object>>();
        var prefId = created!["id"].ToString();

        var deleteResponse = await _client.DeleteAsync($"/api/sourcepreferences/{prefId}");
        Assert.Equal(HttpStatusCode.NoContent, deleteResponse.StatusCode);
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `dotnet test src/web-api/NewsSearcher.Api.Tests/ --filter SourcePreferenceControllerTests -v n`
Expected: All 4 tests FAIL.

- [ ] **Step 3: Create source preference DTOs**

Create `src/web-api/NewsSearcher.Api/Models/DTOs/SourcePreference/SourcePreferenceDto.cs`:

```csharp
namespace NewsSearcher.Api.Models.DTOs.SourcePreference;

public class SourcePreferenceDto
{
    public Guid Id { get; set; }
    public string Type { get; set; } = null!;
    public string Target { get; set; } = null!;
    public bool IsSystemDefault { get; set; }
}
```

Create `src/web-api/NewsSearcher.Api/Models/DTOs/SourcePreference/CreateSourcePreferenceRequest.cs`:

```csharp
using System.ComponentModel.DataAnnotations;

namespace NewsSearcher.Api.Models.DTOs.SourcePreference;

public class CreateSourcePreferenceRequest
{
    [Required]
    public string Type { get; set; } = null!;

    [Required, MaxLength(500)]
    public string Target { get; set; } = null!;
}
```

- [ ] **Step 4: Create SourcePreferenceController**

Create `src/web-api/NewsSearcher.Api/Controllers/SourcePreferenceController.cs`:

```csharp
using System.Security.Claims;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using NewsSearcher.Api.Data;
using NewsSearcher.Api.Models.DTOs.SourcePreference;
using NewsSearcher.Api.Models.Entities;

namespace NewsSearcher.Api.Controllers;

[ApiController]
[Route("api/[controller]")]
[Authorize]
public class SourcePreferencesController : ControllerBase
{
    private static readonly List<(PreferenceType Type, string Target)> SystemDefaults =
    [
        (PreferenceType.Blocklist, "theonion.com"),
        (PreferenceType.Blocklist, "babylonbee.com"),
        (PreferenceType.Blocklist, "clickhole.com"),
        (PreferenceType.Blocklist, "waterfordwhispersnews.com"),
    ];

    private readonly AppDbContext _db;

    public SourcePreferencesController(AppDbContext db)
    {
        _db = db;
    }

    private string UserId => User.FindFirstValue(ClaimTypes.NameIdentifier)!;

    [HttpGet]
    public async Task<IActionResult> GetPreferences()
    {
        var userPrefs = await _db.SourcePreferences
            .Where(s => s.UserId == UserId)
            .ToListAsync();

        var systemPrefs = SystemDefaults.Select(d => new SourcePreferenceDto
        {
            Id = Guid.Empty,
            Type = d.Type.ToString(),
            Target = d.Target,
            IsSystemDefault = true
        });

        var userPrefDtos = userPrefs.Select(s => new SourcePreferenceDto
        {
            Id = s.Id,
            Type = s.Type.ToString(),
            Target = s.Target,
            IsSystemDefault = false
        });

        return Ok(systemPrefs.Concat(userPrefDtos));
    }

    [HttpPost]
    public async Task<IActionResult> AddPreference(CreateSourcePreferenceRequest request)
    {
        if (!Enum.TryParse<PreferenceType>(request.Type, true, out var prefType))
            return BadRequest(new { error = "Type must be 'Blocklist' or 'Priority'" });

        var pref = new SourcePreference
        {
            UserId = UserId,
            Type = prefType,
            Target = request.Target.ToLowerInvariant(),
            IsSystemDefault = false
        };

        _db.SourcePreferences.Add(pref);
        await _db.SaveChangesAsync();

        return Ok(new SourcePreferenceDto
        {
            Id = pref.Id,
            Type = pref.Type.ToString(),
            Target = pref.Target,
            IsSystemDefault = false
        });
    }

    [HttpDelete("{id:guid}")]
    public async Task<IActionResult> DeletePreference(Guid id)
    {
        var pref = await _db.SourcePreferences
            .FirstOrDefaultAsync(s => s.Id == id && s.UserId == UserId);

        if (pref == null)
            return NotFound();

        _db.SourcePreferences.Remove(pref);
        await _db.SaveChangesAsync();

        return NoContent();
    }
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `dotnet test src/web-api/NewsSearcher.Api.Tests/ --filter SourcePreferenceControllerTests -v n`
Expected: All 4 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/web-api/
git commit -m "feat: add source preference controller with blocklist/priority CRUD and system defaults"
```

---

## Task 9: Python ML Service Skeleton

**Files:**
- Create: `src/ml-service/requirements.txt`
- Create: `src/ml-service/app/__init__.py`
- Create: `src/ml-service/app/main.py`
- Create: `src/ml-service/app/routers/__init__.py`
- Create: `src/ml-service/app/routers/health.py`
- Create: `src/ml-service/tests/__init__.py`
- Create: `src/ml-service/tests/test_health.py`
- Create: `src/ml-service/Dockerfile`

- [ ] **Step 1: Write failing health check test**

Create `src/ml-service/tests/__init__.py` (empty file).

Create `src/ml-service/tests/test_health.py`:

```python
from fastapi.testclient import TestClient


def test_health_check():
    from app.main import app

    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "qdrant" in data
    assert "database" in data
```

- [ ] **Step 2: Create requirements.txt**

Create `src/ml-service/requirements.txt`:

```
fastapi==0.115.0
uvicorn[standard]==0.30.0
httpx==0.27.0
psycopg2-binary==2.9.9
qdrant-client==1.11.0
pytest==8.3.0
```

- [ ] **Step 3: Set up Python environment and verify test fails**

Run from `src/ml-service/`:
```bash
python -m venv .venv
source .venv/bin/activate  # or .venv/Scripts/activate on Windows
pip install -r requirements.txt
pytest tests/test_health.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'app'`

- [ ] **Step 4: Create the FastAPI app and health router**

Create `src/ml-service/app/__init__.py` (empty file).

Create `src/ml-service/app/routers/__init__.py` (empty file).

Create `src/ml-service/app/routers/health.py`:

```python
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "qdrant": "not_connected",
        "database": "not_connected",
    }
```

Create `src/ml-service/app/middleware.py`:

```python
import os

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


class ApiKeyMiddleware(BaseHTTPMiddleware):
    """Validates X-Api-Key header on all requests except /health."""

    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/health":
            return await call_next(request)

        expected_key = os.environ.get("ML_SERVICE_API_KEY")
        if not expected_key:
            return await call_next(request)  # No key configured = no auth required

        provided_key = request.headers.get("X-Api-Key")
        if provided_key != expected_key:
            return JSONResponse(status_code=401, content={"error": "Invalid API key"})

        return await call_next(request)
```

Create `src/ml-service/app/main.py`:

```python
from fastapi import FastAPI
from app.middleware import ApiKeyMiddleware
from app.routers import health

app = FastAPI(title="News Searcher ML Service")

app.add_middleware(ApiKeyMiddleware)
app.include_router(health.router)
```

- [ ] **Step 5: Run test to verify it passes**

Run from `src/ml-service/`:
```bash
pytest tests/test_health.py -v
```
Expected: 1 test PASSED.

- [ ] **Step 6: Create Dockerfile**

Create `src/ml-service/Dockerfile`:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 7: Commit**

```bash
git add src/ml-service/
git commit -m "feat: add python ml service skeleton with fastapi and health endpoint"
```

---

## Task 10: MlServiceClient & Integration Verification

**Files:**
- Create: `src/web-api/NewsSearcher.Api/Services/MlServiceClient.cs`

- [ ] **Step 1: Create MlServiceClient**

This is the ASP.NET HTTP client that talks to the Python service. For now it just checks the health endpoint.

Create `src/web-api/NewsSearcher.Api/Services/MlServiceClient.cs`:

```csharp
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
```

- [ ] **Step 2: Register MlServiceClient in Program.cs**

Add after the `AddHttpClient` line in `Program.cs`:

```csharp
builder.Services.AddScoped<MlServiceClient>();
```

- [ ] **Step 3: Verify build**

Run from `src/web-api/`:
```bash
dotnet build
```
Expected: Build succeeded.

- [ ] **Step 4: Run all tests**

Run from `src/web-api/`:
```bash
dotnet test --verbosity normal
```
Expected: All 14 tests PASS (4 auth + 6 profile + 4 source preference).

- [ ] **Step 5: Commit**

```bash
git add src/web-api/NewsSearcher.Api/Services/MlServiceClient.cs src/web-api/NewsSearcher.Api/Program.cs
git commit -m "feat: add ml service client for asp.net to python communication"
```

---

## Task 11: Full Docker Compose Verification

- [ ] **Step 1: Build and start all services**

Run from repo root:
```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build -d
```
Expected: All 4 services start. Check with `docker compose ps`.

- [ ] **Step 2: Verify health endpoints**

```bash
curl http://localhost:8000/health
```
Expected: `{"status":"healthy","qdrant":"not_connected","database":"not_connected"}`

Verify API key protection (should fail without key):
```bash
curl http://localhost:8000/some-endpoint
```
Expected: `{"error":"Invalid API key"}` (401)

```bash
curl -X POST http://localhost:5000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"TestPass123"}'
```
Expected: `{"token":"eyJ..."}`

- [ ] **Step 3: Stop services**

```bash
docker compose down
```

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat: complete infrastructure and core api foundation"
```

---

## Summary

After completing this plan, you have:

- **Docker Compose** running PostgreSQL, Qdrant, ASP.NET API, and Python ML service
- **ASP.NET Web API** with:
  - JWT authentication (register/login)
  - User interest profile CRUD with versioning
  - Source preference management (blocklist/priority) with system defaults
  - HTTP client for communicating with the Python ML service
- **Python ML service** skeleton with FastAPI and health endpoint
- **14 passing integration tests** covering all API endpoints
- **Database schema** with migrations for users, profiles, interests, and source preferences

**Next plan:** Plan 2 (Ingestion Pipeline) builds the source plugin system and article storage on top of this foundation.
