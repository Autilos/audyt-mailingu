<?php
/**
 * Plugin Name: MKpK – porównywarka newsletterów
 * Description: Liczby dla strony /porownywarka-newsletterow/ (jeden plik JSON) i formularz „Dodaj swój sklep”.
 *
 * Źródło: repo Autilos/audyt-mailingu, katalog porownywarka/wp/. Miejsce na serwerze: wp-content/mu-plugins/.
 *
 * - mkpk_porownywarka_dane(): czyta wp-content/uploads/mkpk-porownywarka/dane.json (generuje porownywarka/generuj_dane.py).
 * - admin-ajax.php?action=mkpk_porownywarka: zgłoszenie sklepu. Zapis we Flamingo (kanał mkpk-porownywarka)
 *   + powiadomienie na wnowak@autilo.eu. Do zgłaszającego NIE idzie żaden automatyczny mail — wynik wysyła Wojtek.
 * - Ochrona jak w formularzu kontaktu: pole-pułapka, limit 5 zgłoszeń na godzinę z IP, reCAPTCHA v3
 *   (mkpk_recaptcha_sprawdz z motywu, akcja „porownywarka”).
 */

if (!defined('ABSPATH')) {
	exit;
}

define('MKPK_POROWNYWARKA_ODBIORCA', 'wnowak@autilo.eu');
define('MKPK_POROWNYWARKA_DNI', 14);

function mkpk_porownywarka_plik() {
	$u = wp_upload_dir(null, false);
	return trailingslashit($u['basedir']) . 'mkpk-porownywarka/dane.json';
}

/** Dane dla szablonu. Brak pliku albo zły JSON = pusta tablica (szablon pokazuje „dane w przygotowaniu”). */
function mkpk_porownywarka_dane() {
	static $dane = null;
	if ($dane !== null) {
		return $dane;
	}
	$dane = [];
	$plik = mkpk_porownywarka_plik();
	if (is_readable($plik)) {
		$j = json_decode((string) file_get_contents($plik), true);
		if (is_array($j) && !empty($j['branze'])) {
			$dane = $j;
		} else {
			error_log('MKpK porównywarka: nieczytelny plik danych ' . $plik);
		}
	}
	return $dane;
}

/** Branże do wyboru w formularzu: te z kartą + „inne” z pliku + „Inna”. */
function mkpk_porownywarka_branze() {
	$d = mkpk_porownywarka_dane();
	$lista = [];
	foreach (array_merge($d['branze'] ?? [], $d['inne_branze'] ?? []) as $b) {
		if (!empty($b['nazwa'])) {
			$lista[] = (string) $b['nazwa'];
		}
	}
	$lista[] = 'Inna';
	return array_values(array_unique($lista));
}

/** „https://www.Sklep.pl/kategoria?x=1” → „sklep.pl”. Niepoprawny adres = ''. */
function mkpk_porownywarka_domena($adres) {
	$a = strtolower(trim((string) $adres));
	if ($a === '') {
		return '';
	}
	if (!preg_match('#^[a-z][a-z0-9+.-]*://#', $a)) {
		$a = 'http://' . $a;
	}
	$host = (string) wp_parse_url($a, PHP_URL_HOST);
	$host = preg_replace('/^www\./', '', $host);
	if (!preg_match('/^(?=.{4,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$/', $host)) {
		return '';
	}
	return $host;
}

add_action('wp_ajax_mkpk_porownywarka', 'mkpk_porownywarka_obsluga');
add_action('wp_ajax_nopriv_mkpk_porownywarka', 'mkpk_porownywarka_obsluga');

function mkpk_porownywarka_obsluga() {
	$p = wp_unslash($_POST);
	$ok_odp = ['message' => 'Dziękuję. Zapiszę się do newslettera Twojego sklepu, a wynik porównania wyślę na podany adres e-mail w ciągu około ' . MKPK_POROWNYWARKA_DNI . ' dni.'];

	// Pole-pułapka: wypełnione = bot. Udajemy sukces, nic nie zapisujemy.
	if (!empty($p['firma_www'])) {
		wp_send_json_success($ok_odp);
	}

	$ip = $_SERVER['REMOTE_ADDR'] ?? '';
	$klucz_ip = 'mkpk_porown_ip_' . md5($ip);
	$licznik = (int) get_transient($klucz_ip);
	if ($licznik >= 5) {
		wp_send_json_error(['message' => 'Z jednego adresu można wysłać 5 zgłoszeń na godzinę. Spróbuj później albo napisz bezpośrednio na ' . MKPK_POROWNYWARKA_ODBIORCA . '.']);
	}

	if (function_exists('mkpk_recaptcha_sprawdz')) {
		$spr = mkpk_recaptcha_sprawdz(sanitize_text_field($p['recaptcha_token'] ?? ''), 'porownywarka');
		if (is_wp_error($spr)) {
			wp_send_json_error(['message' => $spr->get_error_message()]);
		}
	} else {
		error_log('MKpK porównywarka: brak mkpk_recaptcha_sprawdz (motyw) - weryfikacja reCAPTCHA pominięta');
	}

	$adres = mb_substr(sanitize_text_field($p['sklep'] ?? ''), 0, 200);
	$domena = mkpk_porownywarka_domena($adres);
	$branze = mkpk_porownywarka_branze();
	$branza = in_array((string) ($p['branza'] ?? ''), $branze, true) ? (string) $p['branza'] : '';
	$email = sanitize_email($p['email'] ?? '');
	$zgoda = !empty($p['zgoda']);
	$zrodlo = substr(preg_replace('/[^a-z0-9-]/', '', strtolower((string) ($p['zrodlo'] ?? ''))), 0, 60);

	$bledy = [];
	if ($domena === '') $bledy[] = 'adres sklepu (np. twojsklep.pl)';
	if ($branza === '') $bledy[] = 'branżę';
	if (!is_email($email)) $bledy[] = 'poprawny adres e-mail';
	if (!$zgoda) $bledy[] = 'zgodę';
	if ($bledy) {
		wp_send_json_error(['message' => 'Uzupełnij: ' . implode(', ', $bledy) . '.']);
	}

	set_transient($klucz_ip, $licznik + 1, HOUR_IN_SECONDS);

	if (!mkpk_porownywarka_zapisz($domena, $adres, $branza, $email, $zrodlo, $ip, esc_url_raw($_SERVER['HTTP_REFERER'] ?? ''))) {
		wp_send_json_error(['message' => 'Nie udało się wysłać zgłoszenia. Napisz proszę bezpośrednio na ' . MKPK_POROWNYWARKA_ODBIORCA . '.']);
	}
	wp_send_json_success($ok_odp);
}

/**
 * Zapis zgłoszenia (po walidacji): Flamingo + powiadomienie do Wojtka. Do zgłaszającego nic nie idzie.
 * Zwraca true, jeśli zadziałał zapis albo mail.
 */
function mkpk_porownywarka_zapisz($domena, $adres, $branza, $email, $zrodlo, $ip = '', $url = '') {
	$teraz = wp_date('Y-m-d H:i');
	$termin = wp_date('Y-m-d', time() + MKPK_POROWNYWARKA_DNI * DAY_IN_SECONDS);
	$temat = 'Porównywarka: nowy sklep do obserwacji ' . $domena . ($zrodlo ? ' [' . $zrodlo . ']' : '');
	$tresc = "Sklep: $domena\nWpisany adres: $adres\nBranża: $branza\nE-mail do wyniku: $email\nŹródło: " . ($zrodlo ?: '-')
		. "\nZgoda: tak\nData zgłoszenia: $teraz\nWynik do wysłania: około $termin\n\n"
		. "Do zrobienia: zapisać skrzynkę obserwacyjną do newslettera sklepu (dopisać do sklepy.json), po "
		. MKPK_POROWNYWARKA_DNI . " dniach przygotować szkic wyniku na " . MKPK_POROWNYWARKA_ODBIORCA . ".\n"
		. "Zgłaszający nie dostał żadnego automatycznego maila.\n";

	// 1. Zapis we Flamingo (panel WP → Flamingo → Wiadomości przychodzące, kanał mkpk-porownywarka).
	$zapisano = false;
	if (class_exists('Flamingo_Inbound_Message')) {
		// Flamingo przypina kanał tylko do istniejącego terminu — bez tego zgłoszenia nie dałoby się filtrować.
		if (!term_exists('mkpk-porownywarka', Flamingo_Inbound_Message::channel_taxonomy)) {
			wp_insert_term('Porównywarka newsletterów', Flamingo_Inbound_Message::channel_taxonomy, ['slug' => 'mkpk-porownywarka']);
		}
		$m = Flamingo_Inbound_Message::add([
			'channel' => 'mkpk-porownywarka',
			'subject' => $temat,
			'from' => $email,
			'from_name' => $domena,
			'from_email' => $email,
			'fields' => ['sklep' => $domena, 'adres' => $adres, 'branza' => $branza, 'email' => $email, 'zrodlo' => $zrodlo, 'zgoda' => 'tak', 'wynik_do' => $termin],
			'meta' => ['remote_ip' => $ip, 'url' => $url, 'date' => $teraz],
		]);
		$zapisano = (bool) $m;
	}

	// 2. Powiadomienie tylko do Wojtka (Reply-To = zgłaszający, żeby odpisać ręcznie).
	$wyslano = wp_mail(MKPK_POROWNYWARKA_ODBIORCA, $temat, $tresc, ['Reply-To: ' . $email]);
	if (!$wyslano) {
		error_log('MKpK porównywarka: wp_mail nie wysłał (zapis we Flamingo: ' . ($zapisano ? 'tak' : 'nie') . ')');
	}
	return $zapisano || $wyslano;
}
