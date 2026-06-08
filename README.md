# trinidadmarroquin.com

Personal site for Trinidad Marroquin, built with [Hugo](https://gohugo.io/) and the [PaperMod](https://github.com/adityatelange/hugo-PaperMod) theme.

The site is intentionally simple: fast static pages, readable content, and practical writing about SRE, DevOps, Kubernetes, Terraform, Packer, Rancher, Concourse, and observability.

## Local Development

Install Hugo, then run:

```bash
hugo server
```

Build the static site:

```bash
hugo
```

Generated files are written to `public/`.

## Content

Main pages live in `content/`:

- `content/_index.md` - home page
- `content/about.md` - about page
- `content/projects.md` - project writeups
- `content/resume.md` - resume page
- `content/posts/` - blog posts

Site configuration lives in `hugo.toml`.

## Resume

The resume page links to `/resume.pdf`. To publish a PDF resume, add it here:

```text
static/resume.pdf
```

Hugo will serve it at:

```text
https://trinidadmarroquin.com/resume.pdf
```

## Theme

This site uses PaperMod from `themes/PaperMod`. Keep theme customizations minimal so the site remains easy to update and maintain.
