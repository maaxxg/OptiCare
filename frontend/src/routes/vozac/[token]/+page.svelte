<script lang="ts">
	import logo from '#lib/assets/opticare-logo.svg';
	import {
		getDriverRoute,
		updateDriverStopStatus,
		formatRouteDate,
		getNavigationUrl,
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

	// Odabrani status meni za detaljne statuse
	let activeStatusMenuStopId = $state<string | null>(null);

	onMount(async () => {
		try {
			route = await getDriverRoute(token);
		} catch {
			error = 'Nije moguće učitati rutu za navedeni token.';
		} finally {
			loading = false;
		}
	});

	async function handleQuickToggle(stop: DriverStop) {
		if (!route) return;
		const newStatus: StopStatus = stop.status === 'picked_up' ? 'pending' : 'picked_up';
		stop.status = newStatus;
		await updateDriverStopStatus(token, stop.id, newStatus);
	}

	async function handleSetStatus(stop: DriverStop, newStatus: StopStatus) {
		if (!route) return;
		stop.status = newStatus;
		activeStatusMenuStopId = null;
		await updateDriverStopStatus(token, stop.id, newStatus);
	}

	function toggleStatusMenu(stopId: string, e: MouseEvent) {
		e.stopPropagation();
		activeStatusMenuStopId = activeStatusMenuStopId === stopId ? null : stopId;
	}

	// Broj putnika koji još nisu ukrcani niti iskrcani
	let remainingCount = $derived(
		route
			? route.stops.filter((s) => s.status !== 'picked_up' && s.status !== 'dropped_off').length
			: 0
	);

	function getStatusLabel(status: StopStatus): string {
		switch (status) {
			case 'picked_up':
				return 'Ukrcan';
			case 'arrived':
				return 'Stigao';
			case 'dropped_off':
				return 'Iskrcan';
			case 'no_show':
				return 'Pacijenta nema';
			case 'delayed':
				return 'Kasnim';
			default:
				return 'Čeka';
		}
	}
</script>

<svelte:head>
	<title>OptiCare — Ruta za vozača</title>
	<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1" />
</svelte:head>

<div class="driver-page-wrap">
	<main class="driver-mobile-card">
		<!-- Gornji header: naziv vozila i logo -->
		<header class="driver-header">
			<div class="header-left">
				<img src={logo} alt="OptiCare" class="driver-logo" />
				<div>
					<div class="vehicle-title">{route?.vehicleTitle ?? 'Sanitetski prijevoz'}</div>
					<div class="role-badge">{route?.driverRole ?? 'Vozač'}</div>
				</div>
			</div>
			<div class="token-badge" title="Jednodnevni token">
				<span class="token-dot"></span>
				<span class="token-text">Link aktivan</span>
			</div>
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
			<!-- Naslov i datum rute -->
			<div class="route-hero">
				<h1 class="main-title">Ruta prijevoza</h1>
				<p class="subtitle">Preuzimanje pacijenata za današnje termine</p>

				<div class="date-badge">
					{formatRouteDate(route.date)}
				</div>
			</div>

			<!-- Popis stajališta -->
			<section class="stops-container" aria-label="Stajališta rute">
				{#each route.stops as stop (stop.id)}
					<article
						class="stop-row-card"
						class:status-picked={stop.status === 'picked_up'}
						class:status-dropped={stop.status === 'dropped_off'}
						class:status-noshow={stop.status === 'no_show'}
						class:status-delayed={stop.status === 'delayed'}
					>
						<!-- Lijeva kolona: redni broj i vrijeme ukrcaja -->
						<div class="stop-time-col">
							<span class="stop-order">{stop.order}</span>
							<span class="pickup-time-pill">{stop.pickupTime}</span>
						</div>

						<div class="card-vertical-divider"></div>

						<!-- Srednja kolona: Ime, Adresa, Napomena o pokretljivosti, Navigacija -->
						<div class="stop-details-col">
							<h2 class="patient-name-heading">{stop.patientName}</h2>

							<div class="address-line">
								<span class="geo-pin" aria-hidden="true">📍</span>
								<span class="address-text">{stop.address}</span>
							</div>

							<!-- Tipka za navigaciju do adrese (E10-T1 [M]) -->
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

								{#if stop.mobilityNote}
									<span class="mobility-tag">
										♿ {stop.mobilityNote}
									</span>
								{/if}
							</div>
						</div>

						<!-- Desna kolona: Glavna tipka ukrcaja i izbornik statusa -->
						<div class="stop-action-col">
							<!-- Glavni brzi checkbox/gumb za ukrcaj -->
							<button
								type="button"
								class="quick-toggle-btn"
								class:active={stop.status === 'picked_up'}
								onclick={() => handleQuickToggle(stop)}
								aria-label="Označi pacijenta {stop.patientName} kao ukrcanog"
								title="Klikni za brzo označavanje ukrcaja"
							>
								{#if stop.status === 'picked_up'}
									<span class="check-symbol">✓</span>
								{:else if stop.status === 'dropped_off'}
									<span class="status-symbol">🏠</span>
								{:else if stop.status === 'no_show'}
									<span class="status-symbol">✕</span>
								{:else if stop.status === 'delayed'}
									<span class="status-symbol">⏱</span>
								{/if}
							</button>

							<!-- Dodatne tipke statusa (Stigao, Ukrcan, Iskrcan, Pacijenta nema, Kasnim) -->
							<div class="status-menu-wrap">
								<button
									type="button"
									class="status-menu-trigger"
									onclick={(e) => toggleStatusMenu(stop.id, e)}
									aria-label="Ostali statusi"
								>
									{getStatusLabel(stop.status)} ▾
								</button>

								{#if activeStatusMenuStopId === stop.id}
									<div class="status-dropdown">
										<button
											type="button"
											class="status-opt"
											onclick={() => handleSetStatus(stop, 'arrived')}>📍 Stigao</button
										>
										<button
											type="button"
											class="status-opt"
											onclick={() => handleSetStatus(stop, 'picked_up')}>✓ Ukrcan</button
										>
										<button
											type="button"
											class="status-opt"
											onclick={() => handleSetStatus(stop, 'dropped_off')}>🏥 Iskrcan</button
										>
										<button
											type="button"
											class="status-opt opt-danger"
											onclick={() => handleSetStatus(stop, 'no_show')}>✕ Pacijenta nema</button
										>
										<button
											type="button"
											class="status-opt opt-warning"
											onclick={() => handleSetStatus(stop, 'delayed')}>⏱ Kasnim</button
										>
									</div>
								{/if}
							</div>
						</div>
					</article>
				{/each}
			</section>

			<!-- Donja statistička kartica -->
			<footer class="route-footer-card">
				<div class="footer-stat-col">
					<div class="stat-caption">Preostalo za pokupiti</div>
					<div class="stat-number-row">
						<span class="stat-large-val">{remainingCount}</span>
						<span class="stat-unit-label">putnika</span>
					</div>
				</div>

				<div class="footer-divider"></div>

				<div class="footer-stat-col right-align">
					<div class="stat-caption">Najkasnije vrijeme dolaska u bolnicu</div>
					<div class="stat-deadline-val">{route.hospitalDeadline}</div>
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
		position: relative;
		transition:
			background 0.2s,
			border-color 0.2s;
	}

	.stop-row-card.status-picked {
		background: #eef6eb;
		border-color: #8bbd83;
	}

	.stop-row-card.status-noshow {
		background: #fdf2f2;
		border-color: #f0c0c0;
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
		height: 48px;
		background: #cbdcc8;
		flex-shrink: 0;
	}

	.stop-details-col {
		flex: 1;
		min-width: 0;
	}

	.patient-name-heading {
		font-size: 1.3rem;
		font-weight: 800;
		color: #1a1a1a;
		line-height: 1.2;
		margin-bottom: 4px;
	}

	.address-line {
		display: flex;
		align-items: flex-start;
		gap: 4px;
		font-size: 0.98rem;
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

	.nav-action-bar {
		display: flex;
		align-items: center;
		flex-wrap: wrap;
		gap: 8px;
	}

	/* Tipka za navigaciju (E10-T1 [M]) */
	.btn-navigate {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		background: #1a1a1a;
		color: #ffffff;
		padding: 7px 14px;
		border-radius: 999px;
		font-size: 0.92rem;
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
		font-size: 1rem;
	}

	.mobility-tag {
		background: #e6eee2;
		color: #2e6224;
		border: 1px solid #b6d3b0;
		padding: 4px 10px;
		border-radius: 999px;
		font-size: 0.85rem;
		font-weight: 700;
		line-height: 1.2;
	}

	/* Desna kolona i statusi */
	.stop-action-col {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 6px;
		flex-shrink: 0;
	}

	.quick-toggle-btn {
		width: 44px;
		height: 44px;
		border-radius: 12px;
		border: 2px solid #1a1a1a;
		background: #ffffff;
		display: flex;
		align-items: center;
		justify-content: center;
		cursor: pointer;
		transition:
			background 0.15s,
			transform 0.1s;
	}

	.quick-toggle-btn.active {
		background: #55914a;
		border-color: #3b7431;
	}

	.quick-toggle-btn:active {
		transform: scale(0.93);
	}

	.check-symbol {
		color: #ffffff;
		font-size: 1.5rem;
		font-weight: 900;
		line-height: 1;
	}

	.status-symbol {
		font-size: 1.2rem;
	}

	.status-menu-wrap {
		position: relative;
	}

	.status-menu-trigger {
		background: none;
		border: none;
		font-size: 0.8rem;
		font-weight: 700;
		color: #55874c;
		cursor: pointer;
		padding: 2px 4px;
		white-space: nowrap;
	}

	.status-menu-trigger:hover {
		text-decoration: underline;
	}

	.status-dropdown {
		position: absolute;
		right: 0;
		top: 100%;
		background: #ffffff;
		border: 1.5px solid #222222;
		border-radius: 12px;
		box-shadow: 0 8px 24px rgba(0, 0, 0, 0.18);
		z-index: 100;
		display: flex;
		flex-direction: column;
		min-width: 140px;
		overflow: hidden;
	}

	.status-opt {
		background: none;
		border: none;
		padding: 10px 14px;
		text-align: left;
		font-size: 0.95rem;
		font-weight: 700;
		color: #1a1a1a;
		cursor: pointer;
		transition: background 0.1s;
	}

	.status-opt:hover {
		background: #eef5ec;
	}

	.status-opt.opt-danger {
		color: #c0392b;
	}

	.status-opt.opt-warning {
		color: #b7791f;
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
		font-size: 0.9rem;
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
