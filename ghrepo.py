"""Module containing GitHubRepo data class and functions to perform api calls"""
from dataclasses import dataclass
from datetime import datetime
import re
from typing import Literal
from base64 import b64decode
import textstat
import httpx

Severity = Literal["ok", "low", "high"]
Criteria = tuple[str, Severity]


@dataclass
class GitHubRepo:
    """Class that contains all relevant info about a GitHub repository"""

    name: str
    owner: str
    url: str
    created: datetime
    description: str | None
    topics: list[str] | None
    license: str | None
    updated: datetime
    readme: str | None
    readability: float | None

    @property
    def description_check(self) -> Criteria:
        """Check that description is available"""
        if self.description:
            return "Description Available", "ok"
        else:
            return "No description", "high"

    @property
    def topics_check(self) -> Criteria:
        """Check that enough topics are available"""
        if not self.topics:
            return "No topics", "high"
        if len(self.topics) < 3:
            return "Less than 3 topics", "low"
        topics_txt = ", ".join(self.topics)
        return topics_txt, "ok"

    @property
    def license_check(self) -> Criteria:
        """Check that registered license is available."""
        if not self.license:
            return "No license", "high"
        if self.license == "Other":
            return self.license, "low"
        return self.license, "ok"

    @property
    def last_update_check(self) -> Criteria:
        """Check that the repo was updated in the past year or two."""
        days = (datetime.now(tz=self.updated.tzinfo) - self.updated).days
        date_txt = self.updated.date().isoformat()
        if days < 365:
            return date_txt, "ok"
        if days < 730:
            return date_txt, "low"
        return date_txt, "high"

    @property
    def readme_check(self) -> Criteria:
        """Check that the readme is available"""
        if self.readme:
            return "Readme available", "ok"
        return "No readme", "high"

    @property
    def readability_check(self) -> Criteria:
        """Check that the readme is legible"""
        if not self.readme:
            return "No readme", "high"
        if self.readability > 30:
            return str(self.readability), "ok"
        if self.readability > 20:
            return str(self.readability), "low"
        return str(self.readability), "high"

    def readme_section_check(self, section: str) -> Criteria:
        """Check if the section occurs in the readme."""
        if not self.readme:
            has_section = False
        else:
            pattern = re.compile(f"\\# {section}", re.IGNORECASE)
            has_section = pattern.search(self.readme) is not None

        if has_section:
            return f"{section} available", "ok"
        return f"{section} not available", "high"

    @classmethod
    async def from_api_response(cls, response: dict):
        """Construct a repository data class from a GitHub api response dictionary."""
        readme_txt = await get_readme(response["full_name"])
        return cls(
            name=response["name"],
            owner=response["owner"]["login"],
            url=response["html_url"],
            created=datetime.fromisoformat(response["created_at"]),
            description=response["description"],
            topics=response["topics"] if "topics" in response else None,
            license=response["license"]["name"] if response["license"] else None,
            updated=datetime.fromisoformat(response["updated_at"]),
            readme=readme_txt,
            readability=compute_readability(readme_txt) if readme_txt is not None else None,
        )


async def get_readme(full_name: str, token: str | None = None) -> str | None:
    """Get readme for a repository."""
    api_url = f"https://api.github.com/repos/{full_name}/readme"
    head = {"Authorization": f"Bearer {token}"} if token else {}
    async with httpx.AsyncClient() as client:
        readme_response = await client.get(api_url, headers=head)
        if readme_response.status_code != 200:
            return None
        readme_b64 = readme_response.json().get("content")
        return b64decode(readme_b64).decode()


def compute_readability(readme_txt: str):
    """Compute readability from readme markdown text."""
    # TODO: strip markdown before computing readability
    return textstat.textstat.flesch_reading_ease(readme_txt)


async def get_org_repos(org: str, token: str | None = None) -> list[GitHubRepo]:
    """Get all the public repos for an organisation."""
    head = {"Authorization": f"Bearer {token}"} if token else {}
    repos = []
    async with httpx.AsyncClient() as client:
        page = 1
        while True:
            url = f"https://api.github.com/orgs/{org}/repos?page={page}&per_page=100"
            response = await client.get(url, headers=head)
            if response.status_code == 200:
                page_repos = response.json()
                if not page_repos:
                    break
                repos += [await GitHubRepo.from_api_response(repo) for repo in page_repos]
                page += 1
            else:
                response.raise_for_status()
    return repos


def find_token_expiration(token: str):
    """Return the time left on the GH personal access token."""
    res = httpx.get("https://api.github.com/", headers={"Authorization": f"Bearer {token}"})
    res.raise_for_status()
    expiry = datetime.fromisoformat(res.headers["GitHub-Authentication-Token-Expiration"])
    return expiry - datetime.now(tz=expiry.tzinfo)
