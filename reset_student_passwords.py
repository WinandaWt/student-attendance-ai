from student_account_service import sync_student_accounts


def main():
    try:
        result = sync_student_accounts(reset_existing_passwords=True)

        print(f"Password student berhasil direset: {result['updated_count']}")
        print(f"Akun student baru dibuat: {result['created_count']}")
        print(f"Konflik username: {result['conflict_count']}")
        print("Password default student sekarang = NIM masing-masing.")

    except Exception as e:
        print("Error:", e)


if __name__ == "__main__":
    main()
