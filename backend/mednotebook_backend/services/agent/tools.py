"""Anthropic native tool-use definitions for the MedNotebook agent.

These are pure JSON schemas handed to the Claude API in the `tools`
parameter — they describe what each tool does and what arguments it takes,
but contain no execution logic. The dispatcher that actually runs a tool
lives alongside this module.

The descriptions are deliberately verbose: they are the only instructions
Claude gets about when to reach for each tool, so they carry the usage
guidance (call search repeatedly, never guess a document ID, compute
numbers with analyze_csv rather than from retrieved text).
"""

SEARCH_DOCUMENTS_TOOL = {
    "name": "search_documents",
    "description": (
        "Search across the user's uploaded documents using semantic and keyword "
        "search. Use this when you need to find specific information, facts, data "
        "points, or passages from documents. Can search all documents or filter by "
        "project. Returns the most relevant text chunks with source citations. Call "
        "this multiple times with different queries to find different aspects of a "
        "question."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "The search query. Be specific and use medical/scientific "
                    "terminology from the documents. For best results use the key "
                    "concepts you are looking for, not the full question."
                ),
            },
            "project_id": {
                "type": "string",
                "description": (
                    "Optional. Filter results to a specific project UUID. Use "
                    "get_document_list first if you need to find the project ID."
                ),
            },
            "document_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Optional. Filter to specific document UUIDs. Use "
                    "get_document_list first if needed."
                ),
            },
            "limit": {
                "type": "integer",
                "description": (
                    "Number of results to return. Default 8, max 20. Use higher "
                    "values for broad research questions."
                ),
                "default": 8,
            },
        },
        "required": ["query"],
    },
}

GET_DOCUMENT_CONTENT_TOOL = {
    "name": "get_document_content",
    "description": (
        "Retrieve the full text content of a specific document or specific pages. "
        "Use this when you need to read an entire document section, when search "
        "results reference a passage and you need more context around it, or when "
        "the user asks about a specific document by name."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "document_id": {
                "type": "string",
                "description": "UUID of the document to retrieve",
            },
            "pages": {
                "type": "array",
                "items": {"type": "integer"},
                "description": (
                    "Optional. Specific page numbers to retrieve. If omitted, "
                    "returns the full document. For large documents always specify "
                    "pages."
                ),
            },
            "chunk_range": {
                "type": "object",
                "properties": {
                    "start": {"type": "integer"},
                    "end": {"type": "integer"},
                },
                "description": (
                    "Optional. Return chunks from index start to end instead of pages."
                ),
            },
        },
        "required": ["document_id"],
    },
}

ANALYZE_CSV_TOOL = {
    "name": "analyze_csv",
    "description": (
        "Run data analysis on an uploaded CSV or Excel file. Use this when the user "
        "asks about data, trends, statistics, comparisons, or calculations from "
        "spreadsheet data. This tool actually computes real numbers — do not try to "
        "calculate from retrieved text, use this tool instead."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "document_id": {
                "type": "string",
                "description": "UUID of the CSV or Excel document",
            },
            "operation": {
                "type": "string",
                "enum": [
                    "summary",
                    "describe_columns",
                    "filter_rows",
                    "calculate_stats",
                    "find_trends",
                    "compare_groups",
                    "find_outliers",
                    "correlation",
                ],
                "description": "The analysis operation to perform",
            },
            "parameters": {
                "type": "object",
                "description": (
                    "Operation-specific parameters. For filter_rows: {column, "
                    "operator, value}. For calculate_stats: {columns, metrics}. For "
                    "compare_groups: {group_column, value_columns}. For correlation: "
                    "{columns}."
                ),
            },
        },
        "required": ["document_id", "operation"],
    },
}

COMPARE_DOCUMENTS_TOOL = {
    "name": "compare_documents",
    "description": (
        "Compare content between two documents. Use this when the user wants to know "
        "differences or similarities between studies, protocols, datasets, or any two "
        "documents. Returns relevant passages from both documents side by side."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "document_id_1": {"type": "string"},
            "document_id_2": {"type": "string"},
            "aspect": {
                "type": "string",
                "description": (
                    "What aspect to compare. Be specific: 'methodology', 'results', "
                    "'patient demographics', 'inclusion criteria', 'glucose "
                    "measurements', etc."
                ),
            },
        },
        "required": ["document_id_1", "document_id_2", "aspect"],
    },
}

GET_DOCUMENT_LIST_TOOL = {
    "name": "get_document_list",
    "description": (
        "Get a list of all documents and projects available to the user. Always call "
        "this first if the user refers to a document by name, mentions a project, or "
        "if you need document IDs for other tools. Do not guess document IDs."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "project_id": {
                "type": "string",
                "description": "Optional. Filter to a specific project.",
            },
            "file_type": {
                "type": "string",
                "enum": ["pdf", "csv", "excel", "image", "text", "all"],
                "default": "all",
            },
        },
    },
}

SUMMARIZE_DOCUMENT_TOOL = {
    "name": "summarize_document",
    "description": (
        "Get the AI-generated summary of a specific document. Use this for a quick "
        "overview before deciding whether to search deeper into a document. If no "
        "summary exists yet, generates one."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "document_id": {"type": "string"},
            "focus": {
                "type": "string",
                "description": (
                    "Optional. Focus the summary on a specific aspect: 'methodology', "
                    "'results', 'patient population', 'conclusions', etc."
                ),
            },
        },
        "required": ["document_id"],
    },
}

TOOLS: list[dict] = [
    SEARCH_DOCUMENTS_TOOL,
    GET_DOCUMENT_CONTENT_TOOL,
    ANALYZE_CSV_TOOL,
    COMPARE_DOCUMENTS_TOOL,
    GET_DOCUMENT_LIST_TOOL,
    SUMMARIZE_DOCUMENT_TOOL,
]

TOOLS_BY_NAME: dict[str, dict] = {tool["name"]: tool for tool in TOOLS}

TOOL_NAMES: tuple[str, ...] = tuple(TOOLS_BY_NAME)
