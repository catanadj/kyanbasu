def _extract_filter_arg(argv):
    """
    Returns (filter_str, remaining_args).
    Supports:
      -f "project:Work +P1"
      --filter "due.before:2025-10-01 status:pending"
      --filter=project:Work
    """
    filt = None
    out = []
    skip_next = False
    for i, a in enumerate(argv):
        if skip_next:
            skip_next = False
            continue
        if a == "-f" or a == "--filter":
            # take the next token as the filter string (user should quote if spaces)
            if i + 1 < len(argv):
                filt = argv[i + 1]
                skip_next = True
            else:
                filt = ""
        elif a.startswith("--filter="):
            filt = a.split("=", 1)[1]
        else:
            out.append(a)
    return filt, out


def _extract_bg_args(argv):
    """Parse --bg=FILE and --bg-opacity=0.00, return (bg_path_str, opacity_str, remaining_args)."""
    bg = None
    opacity = None
    out = []
    skip = False
    for i, a in enumerate(argv):
        if skip:
            skip = False
            continue
        if a == "--bg":
            if i + 1 < len(argv):
                bg = argv[i + 1]
                skip = True
            else:
                bg = ""
        elif a.startswith("--bg="):
            bg = a.split("=", 1)[1]
        elif a.startswith("--bg-opacity="):
            opacity = a.split("=", 1)[1]
        else:
            out.append(a)
    return bg, opacity, out
