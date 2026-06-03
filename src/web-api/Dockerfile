FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build
WORKDIR /src
COPY Briefer.Api/Briefer.Api.csproj Briefer.Api/
RUN dotnet restore Briefer.Api/Briefer.Api.csproj
COPY Briefer.Api/ Briefer.Api/
RUN dotnet publish Briefer.Api/Briefer.Api.csproj -c Release -o /app

FROM mcr.microsoft.com/dotnet/aspnet:10.0
WORKDIR /app
COPY --from=build /app .
EXPOSE 8080
ENTRYPOINT ["dotnet", "Briefer.Api.dll"]
