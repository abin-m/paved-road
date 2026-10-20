import argparse


def main():
    parser = argparse.ArgumentParser(prog="cli")
    parser.add_argument("name")
    args = parser.parse_args()
    print(f"hello {args.name}")


if __name__ == "__main__":
    main()
