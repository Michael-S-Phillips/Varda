"""Entry point to launch the Varda application."""


def main():
    """Main entry point for the Varda application."""
    from varda.app.bootstrap import initVarda

    initVarda()


if __name__ == "__main__":
    main()
