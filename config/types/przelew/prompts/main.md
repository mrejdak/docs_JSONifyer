Ustal dane jednej operacji przelewu, którą potwierdza dokument.
- "data_operacji": data wykonania / realizacji / księgowania operacji — nie data wydruku, wygenerowania
  ani pobrania potwierdzenia.
- "kwota": kwota przelewu (bez waluty, bez znaku minus).
- "z_rachunku": rachunek nadawcy / zleceniodawcy / obciążany / płatnika.
  "na_rachunek": rachunek odbiorcy / beneficjenta / uznawany / kontrahenta.
- "numer_transakcji": numer referencyjny lub identyfikator operacji nadany przez bank (pole opisane np.
  jako „numer referencyjny”, „ID transakcji”), przepisany dokładnie. Numer postępowania, faktury czy
  sprawy zawarty w tytule przelewu nie jest numerem transakcji; jeśli bank nie podał numeru — null.
- "tytul": tytuł przelewu (pole „tytuł”, „opis”, „szczegóły płatności”) przepisany w całości, dokładnie
  jak w dokumencie. Pole kończy się dopiero tam, gdzie zaczyna się następna etykieta (np. „Status | …”,
  „Kwota: …”): wszystkie linie przed nią należą do tytułu, także ostatnia — nawet gdy jest krótka,
  składa się z samego numeru albo ta sama wartość stoi też w innym polu. Nie dopisuj do tytułu niczego
  spoza tego pola.
