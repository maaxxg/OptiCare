<script lang="ts">
	import logo from '#lib/assets/opticare-logo.svg';
	import {
		getDriverRoute,
		updateDriverStopStatus,
		formatRouteDate,
		getNavigationUrl,
		getMobilityIcon,
		MOBILITY_LABELS,
		type DriverRouteResponse,
		type DriverStop,
		type StopStatus
	} from '#lib/api/driver.js';
	import { page } from '$app/state';
	import { onMount } from 'svelte';

	let token = $derived(page.params.token ?? 'demo');
	let route = $state<DriverRouteResponse | null>(null);
	let loading = $state(true);
	let error = $state('');

	onMount(async () => {
		try {
			route = await getDriverRoute(token);
		} catch (err) {
			error = err instanceof Error ? err.message : 'Nije moguće učitati rutu za navedeni token.';
		} finally {
			loading = false;
		}
	});

	async function handleTogglePickup(stop: DriverStop) {
		if (!route) return;
		const newStatus: StopStatus = stop.status === 'picked_up' ? 'pending' : 'picked_up';
		stop.status = newStatus;
		await updateDriverStopStatus(token, stop.id, newStatus);
	}

	// Broj putnika koji još nisu preuzeti
	let remainingCount = $derived(
		route ? route.stops.filter((s) => s.status !== 'picked_up').length : 0
	);
</script>

<svelte:head>
	<title>OptiCare — Ruta za vozača</title>
	<meta name="viewport" content="width=device-width, initial-scale=1" />
</svelte:head>

<div class="driver-page-wrap">
	<main class="driver-mobile-card">
		<!-- Gornji header: naziv vozila i logo -->
		<header class="driver-header">
			<div class="header-left">
				<img src={logo} alt="OptiCare" class="driver-logo" />
				<div>
					<div class="vehicle-title">{route?.vehicle_title ?? 'Sanitetski prijevoz'}</div>
					<div class="role-badge">Vozač</div>
				</div>
			</div>
			{#if !loading && !error && route}
				<div class="token-badge" title="Jednodnevni token">
					<span class="token-dot"></span>
					<span class="token-text">Link aktivan</span>
				</div>
			{/if}
		</header>

		{#if loading}
			<div class="state-box">
				<div class="spinner"></div>
				<p>Učitavanje rute dana…</p>
			</div>
		{:else if error || !route}
			<div class="state-box error">
				<h2>Nevažeći link</h2>
				<p>{error || 'Ruta za ovaj link nije pronađena ili je istekla.'}</p>
			</div>
		{:else}
			<!-- Naslov i datum rute (formatiran u Europe/Zagreb) -->
			<div class="route-hero">
				<h1 class="main-title">Ruta prijevoza</h1>
				<p class="subtitle">Preuzimanje pacijenata za termine</p>

				<div class="date-badge">
					{formatRouteDate(route.date)}
				</div>
			</div>

			<!-- Popis stajališta -->
			<section class="stops-container" aria-label="Stajališta rute">
				{#each route.stops as stop (stop.id)}
					<article class="stop-row-card" class:status-picked={stop.status === 'picked_up'}>
						<!-- Lijeva kolona: redni broj i vrijeme ukrcaja -->
						<div class="stop-time-col">
							<span class="stop-order">{stop.order}</span>
							<span class="pickup-time-pill">{stop.pickup_time}</span>
						</div>

						<div class="card-vertical-divider"></div>

						<!-- Srednja kolona: Ime, Adresa, Rok u bolnici, Napomena o pokretljivosti, Navigacija -->
						<div class="stop-details-col">
							<h2 class="patient-name-heading">{stop.patient_name}</h2>

							<div class="address-line">
								<span class="geo-pin" aria-hidden="true">📍</span>
								<span class="address-text">{stop.address}</span>
							</div>

							<!-- Oznake: rok u bolnici za pacijenta + prilagođena napomena o pokretljivosti s odgovarajućom ikonom -->
							<div class="meta-tags-bar">
								<span class="deadline-tag">
									🏥 Termin: <strong>{stop.appointment_deadline}</strong>
								</span>

								<span class="mobility-tag">
									<span aria-hidden="true">{getMobilityIcon(stop.mobility_class)}</span>
									<span>
										{MOBILITY_LABELS[stop.mobility_class] ?? stop.mobility_class}{stop.mobility_note
											? ` — ${stop.mobility_note}`
											: ''}
									</span>
								</span>
							</div>

							<!-- Tipka za navigaciju do adrese po stajalištu (E10-T1 [M]) -->
							<div class="nav-action-bar">
								<a
									href={getNavigationUrl(stop.address)}
									target="_blank"
									rel="external noopener noreferrer"
									class="btn-navigate"
									aria-label="Pokreni navigaciju do adrese {stop.address}"
								>
									<span class="nav-icon" aria-hidden="true">🧭</span>
									<span>Navigacija</span>
								</a>
							</div>
						</div>

						<!-- Desna kolona: Pravi pristupačni <button> s aria-pressed za status preuzimanja -->
						<div class="stop-action-col">
							<button
								type="button"
								class="check-box-btn"
								class:checked={stop.status === 'picked_up'}
								aria-pressed={stop.status === 'picked_up'}
								aria-label={stop.status === 'picked_up'
									? `Pacijent ${stop.patient_name} je preuzet. Kliknite za poništavanje.`
									: `Označi pacijenta ${stop.patient_name} kao preuzetog`}
								onclick={() => handleTogglePickup(stop)}
							>
								{#if stop.status === 'picked_up'}
									<span class="checkmark" aria-hidden="true">✓</span>
								{/if}
							</button>
							<span class="check-label">
								{stop.status === 'picked_up' ? 'Preuzet' : 'Čeka'}
							</span>
						</div>
					</article>
				{/each}
			</section>

			<!-- Donja statistička kartica: Još za preuzeti i Prvi termin u bolnici -->
			<footer class="route-footer-card">
				<div class="footer-stat-col">
					<div class="stat-caption">Još za preuzeti</div>
					<div class="stat-number-row">
						<span class="stat-large-val">{remainingCount}</span>
						<span class="stat-unit-label">putnika</span>
					</div>
				</div>

				<div class="footer-divider"></div>

				<div class="footer-stat-col right-align">
					<div class="stat-caption">Prvi termin u bolnici</div>
					<div class="stat-deadline-val">{route.first_appointment_time}</div>
				</div>
			</footer>
		{/if}
	</main>
</div>

<style>
	/* ─── Mobilni omot i kartica (E10-T1 velika slova, optimizirano za terenski rad) ─── */
	.driver-page-wrap {
		min-height: 100dvh;
		background: #ecefe9;
		display: flex;
		justify-content: center;
		padding: 12px;
		font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
	}

	.driver-mobile-card {
		background: #ffffff;
		width: 100%;
		max-width: 480px;
		min-height: 94vh;
		padding: 24px 20px 32px;
		border-radius: 36px;
		box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
		border: 4px solid #1a1a1a;
		display: flex;
		flex-direction: column;
		box-sizing: border-box;
	}

	@media (max-width: 520px) {
		.driver-page-wrap {
			padding: 0;
			background: #ffffff;
		}
		.driver-mobile-card {
			border: none;
			border-radius: 0;
			min-height: 100dvh;
			box-shadow: none;
			padding: 20px 16px 28px;
		}
	}

	/* ─── Header ────────────────────────────────── */
	.driver-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		margin-bottom: 24px;
		border-bottom: 1.5px solid #eef2ec;
		padding-bottom: 14px;
	}

	.header-left {
		display: flex;
		align-items: center;
		gap: 12px;
	}

	.driver-logo {
		height: 40px;
		width: auto;
	}

	.vehicle-title {
		font-size: 1.15rem;
		font-weight: 800;
		color: #1a1a1a;
		line-height: 1.2;
	}

	.role-badge {
		font-size: 0.88rem;
		font-weight: 600;
		color: #55874c;
	}

	.token-badge {
		display: flex;
		align-items: center;
		gap: 6px;
		background: #f0f7ee;
		border: 1px solid #b5d8ae;
		padding: 6px 12px;
		border-radius: 999px;
	}

	.token-dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		background: #46963a;
	}

	.token-text {
		font-size: 0.8rem;
		font-weight: 700;
		color: #276b1c;
	}

	/* ─── Hero naslov i datum ───────────────────── */
	.route-hero {
		margin-bottom: 22px;
	}

	.main-title {
		font-size: 2.3rem;
		font-weight: 900;
		color: #000000;
		letter-spacing: -0.02em;
		line-height: 1.1;
		margin-bottom: 4px;
	}

	.subtitle {
		font-size: 1.1rem;
		color: #555555;
		margin-bottom: 16px;
		font-weight: 500;
	}

	.date-badge {
		display: inline-block;
		background: #edf5ea;
		border: 1.5px solid #b7d6af;
		padding: 10px 22px;
		border-radius: 999px;
		font-size: 1.15rem;
		font-weight: 800;
		color: #1a1a1a;
	}

	/* ─── Popis stajališta ──────────────────────── */
	.stops-container {
		display: flex;
		flex-direction: column;
		gap: 14px;
		margin-bottom: 24px;
		flex: 1;
	}

	.stop-row-card {
		background: #f4f8f2;
		border: 1.5px solid #d5e4d2;
		border-radius: 24px;
		padding: 16px 16px;
		display: flex;
		align-items: center;
		gap: 12px;
		transition:
			background 0.2s,
			border-color 0.2s;
	}

	.stop-row-card.status-picked {
		background: #eef6eb;
		border-color: #8bbd83;
	}

	.stop-time-col {
		display: flex;
		align-items: center;
		gap: 8px;
		flex-shrink: 0;
	}

	.stop-order {
		font-size: 1.3rem;
		font-weight: 900;
		color: #1a1a1a;
		min-width: 16px;
		text-align: center;
	}

	.pickup-time-pill {
		background: #ffffff;
		border: 1.5px solid #222222;
		padding: 8px 14px;
		border-radius: 999px;
		font-size: 1.15rem;
		font-weight: 800;
		color: #1a1a1a;
		box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
	}

	.card-vertical-divider {
		width: 1.5px;
		height: 52px;
		background: #cbdcc8;
		flex-shrink: 0;
	}

	.stop-details-col {
		flex: 1;
		min-width: 0;
	}

	.patient-name-heading {
		font-size: 1.35rem;
		font-weight: 800;
		color: #1a1a1a;
		line-height: 1.2;
		margin-bottom: 4px;
	}

	.address-line {
		display: flex;
		align-items: flex-start;
		gap: 4px;
		font-size: 1rem;
		color: #333333;
		margin-bottom: 8px;
		line-height: 1.25;
	}

	.geo-pin {
		flex-shrink: 0;
		font-size: 1rem;
	}

	.address-text {
		font-weight: 500;
		word-break: break-word;
	}

	.meta-tags-bar {
		display: flex;
		align-items: center;
		flex-wrap: wrap;
		gap: 6px;
		margin-bottom: 10px;
	}

	.deadline-tag {
		background: #ffffff;
		color: #1a1a1a;
		border: 1px solid #bfd3bb;
		padding: 4px 10px;
		border-radius: 999px;
		font-size: 0.88rem;
		font-weight: 600;
	}

	.mobility-tag {
		background: #e6eee2;
		color: #275d21;
		border: 1px solid #b6d3b0;
		padding: 4px 10px;
		border-radius: 999px;
		font-size: 0.85rem;
		font-weight: 700;
		line-height: 1.2;
		display: inline-flex;
		align-items: center;
		gap: 4px;
	}

	/* Tipka za navigaciju (E10-T1 [M]) */
	.nav-action-bar {
		display: flex;
		align-items: center;
		gap: 8px;
	}

	.btn-navigate {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		background: #1a1a1a;
		color: #ffffff;
		padding: 8px 16px;
		border-radius: 999px;
		font-size: 0.95rem;
		font-weight: 700;
		text-decoration: none;
		transition:
			background 0.15s,
			transform 0.1s;
		box-shadow: 0 2px 6px rgba(0, 0, 0, 0.12);
	}

	.btn-navigate:hover {
		background: #333333;
	}

	.btn-navigate:active {
		transform: scale(0.96);
	}

	.nav-icon {
		font-size: 1.05rem;
	}

	/* Desna kolona: Pravi semantički gumb s aria-pressed */
	.stop-action-col {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 4px;
		flex-shrink: 0;
	}

	.check-box-btn {
		width: 48px;
		height: 48px;
		border-radius: 14px;
		border: 2px solid #1a1a1a;
		background: #ffffff;
		display: flex;
		align-items: center;
		justify-content: center;
		cursor: pointer;
		padding: 0;
		transition:
			background 0.15s,
			border-color 0.15s,
			transform 0.1s;
	}

	.check-box-btn.checked {
		background: #55914a;
		border-color: #3b7431;
	}

	.check-box-btn:active {
		transform: scale(0.93);
	}

	.checkmark {
		color: #ffffff;
		font-size: 1.7rem;
		font-weight: 900;
		line-height: 1;
	}

	.check-label {
		font-size: 0.8rem;
		font-weight: 700;
		color: #444444;
	}

	/* ─── Footer statistika ─────────────────────── */
	.route-footer-card {
		background: #edf5ea;
		border: 2px solid #b6d8af;
		border-radius: 28px;
		padding: 20px 22px;
		display: flex;
		align-items: center;
		justify-content: space-between;
		margin-top: auto;
	}

	.footer-stat-col {
		flex: 1;
	}

	.footer-stat-col.right-align {
		text-align: right;
	}

	.stat-caption {
		font-size: 0.95rem;
		font-weight: 700;
		color: #444444;
		margin-bottom: 6px;
		line-height: 1.25;
	}

	.stat-number-row {
		display: flex;
		align-items: baseline;
		gap: 8px;
	}

	.stat-large-val {
		font-size: 2.7rem;
		font-weight: 900;
		color: #1a1a1a;
		line-height: 1;
	}

	.stat-unit-label {
		font-size: 1.4rem;
		font-weight: 800;
		color: #1a1a1a;
	}

	.footer-divider {
		width: 2px;
		height: 60px;
		background: #c2d9be;
		margin: 0 16px;
		flex-shrink: 0;
	}

	.stat-deadline-val {
		font-size: 2.6rem;
		font-weight: 900;
		color: #1a1a1a;
		line-height: 1;
	}

	/* ─── State box (loading/error) ─────────────── */
	.state-box {
		padding: 60px 20px;
		text-align: center;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 16px;
		flex: 1;
		justify-content: center;
	}

	.state-box.error h2 {
		color: #c0392b;
		margin-bottom: 8px;
	}

	.spinner {
		width: 36px;
		height: 36px;
		border: 3.5px solid #d5e5d1;
		border-top-color: #55914a;
		border-radius: 50%;
		animation: spin 0.8s linear infinite;
	}

	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}
</style>
