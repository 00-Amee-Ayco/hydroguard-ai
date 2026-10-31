"""Live regulatory retrieval against the verified HYDROGUARD.regulatory schema."""
import os
from pathlib import Path
import re
from uuid import uuid4
import httpx
from pydantic import ValidationError
from dotenv import dotenv_values
from scripts.zetaris_smoke import Config, SmokeError
from hydroguard.evidence.models import EvidenceSource, ProjectClaim


class ZetarisRetrievalError(RuntimeError):
    """Sanitized runtime failure; never contains credentials or response bodies."""


class ZetarisConfigurationError(ZetarisRetrievalError):
    pass


FIELDS = ("chunk_id", "document_id", "title", "page", "text", "source_type",
          "original_filename", "locator", "issuing_body_or_author", "publication_or_effective_date",
          "original_source_url")
TERMS = {
    "Water": ("water", "groundwater", "baseline", "season", "demand", "users"),
    "Land": ("land", "erosion", "slope", "soil"),
    "Air": ("air", "dust", "emission", "particulate"),
}


def regulatory_query(table: str, claim: ProjectClaim, limit: int = 10) -> str:
    if len(table.split(".")) != 2 or not all(re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", part) for part in table.split(".")):
        raise ZetarisConfigurationError("ZETARIS_REGULATORY_TABLE must be a qualified database.table identifier")
    if not 1 <= limit <= 20 or claim.domain not in TERMS:
        raise ZetarisConfigurationError("Unsupported retrieval domain or row limit")
    words = set(re.findall(r"[a-z]+", claim.text.lower()))
    terms = [term for term in TERMS[claim.domain] if term in words] or [TERMS[claim.domain][0]]
    # Only fixed public topic words enter SQL/logs, never private free-form input.
    relevance = " OR ".join(f"LOWER(text) LIKE '%{term}%'" for term in terms)
    return (f"SELECT {', '.join(FIELDS)} FROM {table} "
            f"WHERE source_type = 'regulatory' AND ({relevance}) ORDER BY chunk_id LIMIT {limit}")


class ZetarisEvidenceRetriever:
    def __init__(self, config: Config, table: str = "HYDROGUARD.regulatory", trace=None, transport=None, project_case_id=None):
        self.config, self.table, self.trace, self.transport = config, table, trace, transport
        self.project_case_id = project_case_id

    @classmethod
    
    def from_environment(cls, trace=None):
        env_file = Path(
            os.environ.get("ZETARIS_ENV_FILE", ".env.local")
        )

        # Do not silently fall back to environment credentials
        # when the selected configuration file is missing.
        if not env_file.is_file():
            raise ZetarisConfigurationError(
                "Zetaris configuration file is unavailable; values omitted"
            )

        try:
            config = Config.load(env_file)
        except SmokeError:
            raise ZetarisConfigurationError(
                "Missing or invalid Zetaris REST configuration; values omitted"
            ) from None

        file_values = dotenv_values(env_file, interpolate=False)

        table = os.environ.get(
            "ZETARIS_REGULATORY_TABLE",
            file_values.get("ZETARIS_REGULATORY_TABLE")
            or "HYDROGUARD.regulatory",
        )

        regulatory = cls(config, table, trace)

        project_table = os.environ.get(
            "ZETARIS_PROJECT_TABLE",
            file_values.get("ZETARIS_PROJECT_TABLE"),
        )

        case_id = os.environ.get(
            "ZETARIS_PROJECT_CASE_ID",
            file_values.get("ZETARIS_PROJECT_CASE_ID"),
        )

        if bool(project_table) != bool(case_id):
            raise ZetarisConfigurationError(
                "Both project table and case ID must be configured together"
            )

        if project_table:
            project = cls(
                config,
                project_table,
                trace,
                project_case_id=case_id,
            )
            return CaseScopedRetriever(regulatory, project, case_id)

        return regulatory


    def retrieve(self, claim: ProjectClaim) -> dict[str, EvidenceSource]:
        fields = FIELDS
        expected_type = "regulatory"
        if self.project_case_id:
            if claim.claim_id != self.project_case_id or claim.domain != "Water":
                raise ZetarisConfigurationError("Project evidence belongs to a different case/domain")
            if not re.fullmatch(r"[a-z0-9-]{1,100}", self.project_case_id):
                raise ZetarisConfigurationError("Invalid project case ID")
            # Validate identifiers using the same verified query builder.
            regulatory_query(self.table, claim)
            fields = FIELDS + ("case_id", "is_synthetic")
            sql = (f"SELECT {', '.join(fields)} FROM {self.table} WHERE source_type = 'project' "
                   f"AND case_id = '{self.project_case_id}' AND is_synthetic = true ORDER BY chunk_id LIMIT 10")
            expected_type = "project"
        else:
            sql = regulatory_query(self.table, claim)
        query_id, request_id = str(uuid4()), str(uuid4())
        if self.trace:
            self.trace.emit("Evidence Investigator", "zetaris_sql_started", "started", sql=sql, query_id=query_id)
        http_status = None
        try:
            with httpx.Client(timeout=self.config.timeout, follow_redirects=False, transport=self.transport) as client:
                response = client.post(self.config.base_url + "/sql-editor/sqls/run", headers={
                    "Authorization": "Bearer " + self.config.api_key, "X-Org-ID": self.config.org_id,
                    "X-Request-ID": request_id}, json={"queryId": query_id, "sql": sql, "source": "SqlEditor", "limit": 10})
            http_status = response.status_code
            if response.status_code != 200:
                raise ZetarisRetrievalError(f"Zetaris HTTP {response.status_code}; response body omitted")
            payload = response.json()
            rows = payload.get("data") if isinstance(payload, dict) else None
            if not isinstance(rows, list):
                raise ZetarisRetrievalError("Zetaris response has no valid row list")
            if len(rows) > 10:
                raise ZetarisRetrievalError("Zetaris returned more rows than the bounded request allowed")
            sources = {}
            for row in rows:
                if not isinstance(row, list) or len(row) != len(fields):
                    raise ZetarisRetrievalError("Zetaris row shape differs from the verified schema")
                record = dict(zip(fields, row))
                if (record["source_type"] != expected_type or not isinstance(record["chunk_id"], str)
                        or not re.fullmatch(r"chunk-[0-9a-f]{64}", record["chunk_id"])
                        or not isinstance(record["document_id"], str)
                        or not re.fullmatch(r"doc-[0-9a-f]{64}", record["document_id"])
                        or not isinstance(record["text"], str) or not record["text"].strip()):
                    raise ZetarisRetrievalError("Zetaris row contains invalid citation/provenance fields")
                if self.project_case_id and (record["case_id"] != self.project_case_id or
                        str(record["is_synthetic"]).lower() != "true"):
                    raise ZetarisRetrievalError("Project evidence lacks verified case/synthetic markers")
                try:
                    source = EvidenceSource(source_id=record["chunk_id"], document_id=record["document_id"],
                        document_title=record["title"], page=record["page"], chunk_id=record["chunk_id"],
                        provenance="synthetic" if self.project_case_id else "government", domain=claim.domain,
                        kind="project" if self.project_case_id else "basis", text=record["text"],
                        source_type=expected_type, is_synthetic=bool(self.project_case_id), case_id=self.project_case_id, original_filename=record["original_filename"], locator=record["locator"],
                        issuing_body_or_author=record["issuing_body_or_author"],
                        publication_or_effective_date=record["publication_or_effective_date"],
                        original_source_url=record["original_source_url"])
                except ValidationError:
                    raise ZetarisRetrievalError("Zetaris row has missing or invalid provenance; values omitted") from None
                if source.source_id in sources:
                    raise ZetarisRetrievalError("Duplicate citation ID in Zetaris response")
                sources[source.source_id] = source
        except (httpx.HTTPError, ValueError):
            if self.trace:
                self.trace.emit("Evidence Investigator", "zetaris_sql_failed", "failed", query_id=query_id, http_status=http_status)
            raise ZetarisRetrievalError("Zetaris connection, timeout or response parsing failed; details omitted") from None
        except ZetarisRetrievalError:
            if self.trace:
                self.trace.emit("Evidence Investigator", "zetaris_sql_failed", "failed", query_id=query_id, http_status=http_status)
            raise
        if self.trace:
            self.trace.emit("Evidence Investigator", "zetaris_sql_completed", source_ids=tuple(sources),
                            sql=sql, query_id=query_id, http_status=response.status_code, row_count=len(sources))
        return sources


class CaseScopedRetriever:
    """Regulatory references plus separately retrieved, explicitly scoped project data."""
    def __init__(self, regulatory, project, case_id):
        self.regulatory, self.project, self.case_id = regulatory, project, case_id

    def retrieve(self, claim):
        sources = self.regulatory.retrieve(claim)
        if claim.claim_id == self.case_id and claim.domain == "Water":
            project = self.project.retrieve(claim)
            if set(project) & set(sources):
                raise ZetarisRetrievalError("Project/regulatory citation ID collision")
            sources.update(project)
        return sources
