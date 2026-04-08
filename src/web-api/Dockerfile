FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build
WORKDIR /src
COPY NewsSearcher.Api/NewsSearcher.Api.csproj NewsSearcher.Api/
RUN dotnet restore NewsSearcher.Api/NewsSearcher.Api.csproj
COPY NewsSearcher.Api/ NewsSearcher.Api/
RUN dotnet publish NewsSearcher.Api/NewsSearcher.Api.csproj -c Release -o /app

FROM mcr.microsoft.com/dotnet/aspnet:10.0
WORKDIR /app
COPY --from=build /app .
EXPOSE 8080
ENTRYPOINT ["dotnet", "NewsSearcher.Api.dll"]
