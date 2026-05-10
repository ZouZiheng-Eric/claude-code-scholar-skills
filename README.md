# Claude Code Scholar Skills

Two Claude Code skills for academic research workflows: discovering papers from the web and managing your local paper repository.

## Skills

### [literature-scout](./literature-scout/)

Automated web literature collection. Searches arXiv, Semantic Scholar, DBLP, and GitHub for research papers and open-source projects, produces structured reports with search strategy recording, and supports batch archiving.

### [paper-survey](./paper-survey/)

Paper management and literature survey workflow. Organizes PDFs into a categorized repository (`papers/`), tracks reading progress, writes structured reading notes, and synthesizes topic surveys.

## Typical Workflow

```
/literature-scout diffusion weather forecasting   → discovers papers from the web
  ↓ report shows archive candidates [1] [2] [3]...
  ↓ user says "归档 1 3" or "archive all"
/paper-survey                                      → downloads, renames, classifies
  ↓ user starts a topic survey
/paper-survey                                      → writes reading notes and synthesis
```

## Installation

Copy both skill directories to your Claude Code skills folder:

```bash
cp -r literature-scout paper-survey ~/.claude/skills/
```

### Dependencies

- **literature-scout**: No additional dependencies (Python standard library only)
- **paper-survey**: `pip install pypdf>=3.0.0`

### Optional

- Set `S2_API_KEY` env var for Semantic Scholar higher rate limits (free key: https://www.semanticscholar.org/product/api#api-key)

## Requirements

- [Claude Code](https://claude.ai/code) CLI or desktop app
- Python 3.10+

## License

MIT
