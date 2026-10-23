"""User-facing CLI copy. Keep format placeholders when customizing these messages."""

CLI_DESCRIPTION = (
    "Generate and validate a pinned institutional service before creating its Git baseline."
)
CLI_EPILOG = (
    "Validation always uses uv with network access allowed. "
    "Git initialization and the initial main commit are required. "
    "The template ZIP must have an accompanying .sha256 file."
)

# Interactive questions. Branch/version defaults and validation rules stay in cli.py.
PROJECT_NAME_PROMPT = (
    "Project name (at least two lowercase words separated by '-' or '_', "
    "e.g. gen_ai_demo; creates folder 'gen-ai-demo' and package 'gen_ai_demo'): "
)
TEMPLATE_VERSION_PROMPT = (
    "Template version to use [{version}] "
    "(press Enter to accept, or enter another version available from this source): "
)
WORK_BRANCH_PROMPT = (
    "Working branch [main] (press Enter to stay on main, or enter a branch name "
    "to create after the initial commit, e.g. feature/my-service): "
)
DEFAULT_DESCRIPTION = "Generated institutional Python service"
DESCRIPTION_PROMPT = (
    "Service description [{description}] "
    "(briefly describe the service's purpose; do not include credentials or secrets): "
)

# Option descriptions shown by --help.
NAME_HELP = (
    "Service name: at least two lowercase segments separated by '-' or '_', e.g. gen_ai_demo"
)
BRANCH_HELP = (
    "Working branch to create after the initial main commit; "
    "when omitted, prompt for a branch (Enter keeps main)"
)
PROJECT_VERSION_HELP = "Initial service MAJOR.MINOR.PATCH, independent of the template version"
TEMPLATE_VERSION_HELP = (
    "Published template MAJOR.MINOR.PATCH to use; when omitted, "
    "show the latest available version and prompt for a selection"
)
DESCRIPTION_HELP = "Nonsecret service description, preserved verbatim; prompt when omitted"
OUTPUT_DIR_HELP = (
    "Existing parent directory for the new service folder; default: current directory; "
    "must be outside any Git repository or Python project"
)
ARCHIVE_HELP = (
    "Local ZIP with a portable basename (letters/digits, _ or -; max 128 characters) "
    "and mandatory adjacent .sha256 file; use this instead of downloading from Nexus"
)
NEXUS_URL_HELP = (
    "Base URL of the Nexus Raw repository, without template path or filename; "
    "default: ARCHETYPE_NEXUS_URL or loopback Nexus; "
    "requires ARCHETYPE_NEXUS_TEMPLATE_PATH and excludes --archive"
)

# Main workflow output. Error details from validation keep their existing wording.
LOCAL_TEMPLATE_VERSION = "Template version in the local archive: {version}"
LATEST_TEMPLATE_VERSION = "Latest published template version available in Nexus: {version}"
UNAVAILABLE_TEMPLATE_VERSION = "Selected archetype version is not available from this source."
SCRATCH_CREATED = "Scratch: {path}"
PROJECT_CREATED = "Created {name}"
ERROR = "Error: {message}"
GENERATION_FAILED = (
    "Error: Generation failed; destination was not promoted. Check inputs and local tooling."
)
RENDERING_FAILED = (
    "Error: Template rendering or local validation failed; destination was not promoted."
)
