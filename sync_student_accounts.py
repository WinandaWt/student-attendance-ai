from student_account_service import sync_student_accounts


def main():
    try:
        result = sync_student_accounts(reset_existing_passwords=False)

        print(f"Akun student berhasil dibuat: {result['created_count']}")
        print(f"Akun student yang sudah ada: {result['skipped_count']}")
        print(f"Konflik username: {result['conflict_count']}")
        print("Password default untuk student = NIM masing-masing.")

    except Exception as e:
        print("Error:", e)


if __name__ == "__main__":
    main()
