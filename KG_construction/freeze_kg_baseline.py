from infra.baseline_snapshot import freeze_current_baseline


def main() -> None:
    baseline_root = freeze_current_baseline()
    print(f"KG baseline 已冻结到: {baseline_root}")


if __name__ == "__main__":
    main()
