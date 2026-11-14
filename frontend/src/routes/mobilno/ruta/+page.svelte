<script lang="ts">
	import {
		getDriverState,
		isDriverLoggedIn,
		logoutDriver,
		togglePickUp,
		type RouteStop
	} from '#lib/stores/driver.js';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { onMount } from 'svelte';

	let driver = $state(getDriverState());

	onMount(() => {
		if (!isDriverLoggedIn()) {
			goto(resolve('/mobilno/login'));
		} else {
			driver = getDriverState();
		}
	});

	function handleToggle(stopId: string) {
		togglePickUp(stopId);
		driver = getDriverState();
	}

	function handleLogout() {
		logoutDriver();
		goto(resolve('/mobilno/login'));
	}

	function goBack() {
		goto(resolve('/mobilno'));
	}

	// Računanje preostalih putnika koji još nisu pokupljeni
	let remainingCount = $derived(driver.stops.filter((s: RouteStop) => !s.pickedUp).length);
</script>

<svelte:head>
	<title>OptiCare Mobilno — Ruta prijevoza</title>
</svelte:head>

<div class="mobile-container">
	<div class="mobile-screen">
		<!-- Gornja navigacijska traka: Vozač i Odjava -->
		<div class="route-top-header">
			<div class="driver-profile-pill">
				<div class="driver-dot"></div>
				<span class="driver-label">{driver.profession || 'Vozač'}</span>
			</div>
			<div class="header-right-actions">
				<button class="back-text-btn" onclick={goBack} title="Natrag na pregled">← Natrag</button>
				<button class="logout-green-btn" onclick={handleLogout}>Odjava</button>
			</div>
		</div>

		<!-- Naslov i podnaslov rute -->
		<div class="route-title-section">
			<h1 class="route-main-title">Ruta prijevoza</h1>
			<p class="route-main-subtitle">Preuzimanje pacijenata za današnje termine</p>

			<div class="date-badge-pill">Utorak, 18. studenoga</div>
		</div>

		<!-- Popis pacijenata na ruti -->
		<div class="stops-list">
			{#each driver.stops as stop (stop.id)}
				<div
					class="stop-card"
					class:picked={stop.pickedUp}
					onclick={() => handleToggle(stop.id)}
					role="button"
					tabindex="0"
					onkeydown={(e) => {
						if (e.key === 'Enter' || e.key === ' ') handleToggle(stop.id);
					}}
				>
					<div class="stop-time-col">
						<span class="stop-index">{stop.order}</span>
						<span class="stop-time-pill">{stop.time}</span>
					</div>

					<div class="stop-divider"></div>

					<div class="stop-info-col">
						<h3 class="patient-name">{stop.patientName}</h3>
						<div class="patient-address">
							<span class="pin-icon">📍</span>
							<span>{stop.address}</span>
						</div>
					</div>

					<div class="stop-checkbox-col">
						<div class="check-box" class:checked={stop.pickedUp} aria-label="Status preuzimanja">
							{#if stop.pickedUp}
								<span class="checkmark">✓</span>
							{/if}
						</div>
					</div>
				</div>
			{/each}
		</div>

		<!-- Donja statistička kartica -->
		<div class="route-footer-stats">
			<div class="stat-col left-col">
				<div class="stat-title">Preostalo za pokupiti</div>
				<div class="stat-value-group">
					<span class="big-number">{remainingCount}</span>
					<span class="unit-text">putnika</span>
				</div>
			</div>

			<div class="stat-vertical-divider"></div>

			<div class="stat-col right-col">
				<div class="stat-title">Najkasnije vrijeme dolaska u bolnicu</div>
				<div class="stat-time-display">{driver.deadline || '09:00'}</div>
			</div>
		</div>
	</div>
</div>

<style>
	.mobile-container {
		min-height: 100dvh;
		display: flex;
		align-items: center;
		justify-content: center;
		background: #f0f2f0;
		padding: 16px;
	}

	.mobile-screen {
		background: #ffffff;
		width: 100%;
		max-width: 412px;
		min-height: 840px;
		padding: 30px 22px 36px;
		border-radius: 40px;
		box-shadow: 0 12px 36px rgba(0, 0, 0, 0.12);
		border: 8px solid #1a1a1a;
		display: flex;
		flex-direction: column;
		justify-content: space-between;
		box-sizing: border-box;
		position: relative;
	}

	@media (max-width: 480px) {
		.mobile-container {
			padding: 0;
			background: #fff;
		}
		.mobile-screen {
			border: none;
			border-radius: 0;
			min-height: 100dvh;
			box-shadow: none;
			padding: 24px 18px 28px;
		}
	}

	/* ─── Top header ────────────────────── */
	.route-top-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		margin-bottom: 22px;
	}

	.driver-profile-pill {
		display: flex;
		align-items: center;
		gap: 12px;
	}

	.driver-dot {
		width: 38px;
		height: 38px;
		background: #609756;
		border-radius: 50%;
		flex-shrink: 0;
	}

	.driver-label {
		font-size: 1.25rem;
		font-weight: 700;
		color: #1a1a1a;
	}

	.header-right-actions {
		display: flex;
		align-items: center;
		gap: 16px;
	}

	.back-text-btn {
		background: none;
		border: none;
		color: #666;
		font-size: 0.95rem;
		font-weight: 600;
		cursor: pointer;
		padding: 0;
	}

	.logout-green-btn {
		background: none;
		border: none;
		color: #4b8543;
		font-size: 1.15rem;
		font-weight: 700;
		cursor: pointer;
		padding: 0;
	}

	/* ─── Title Section ─────────────────── */
	.route-title-section {
		margin-bottom: 24px;
	}

	.route-main-title {
		font-size: 2.25rem;
		font-weight: 800;
		color: #000000;
		margin-bottom: 4px;
		letter-spacing: -0.02em;
	}

	.route-main-subtitle {
		font-size: 1.05rem;
		color: #555;
		margin-bottom: 18px;
		font-weight: 500;
	}

	.date-badge-pill {
		display: inline-block;
		background: #eff5ed;
		padding: 10px 22px;
		border-radius: 999px;
		font-size: 1.08rem;
		font-weight: 700;
		color: #1a1a1a;
	}

	/* ─── Stops List ────────────────────── */
	.stops-list {
		display: flex;
		flex-direction: column;
		gap: 12px;
		margin-bottom: 24px;
		flex: 1;
	}

	.stop-card {
		background: #f4f8f2;
		border-radius: 20px;
		padding: 14px 16px;
		display: flex;
		align-items: center;
		cursor: pointer;
		transition:
			background 0.15s,
			transform 0.08s;
		user-select: none;
	}

	.stop-card:hover {
		background: #ecf3ea;
	}

	.stop-card:active {
		transform: scale(0.99);
	}

	.stop-time-col {
		display: flex;
		align-items: center;
		gap: 10px;
		flex-shrink: 0;
	}

	.stop-index {
		font-size: 1.15rem;
		font-weight: 800;
		color: #1a1a1a;
		min-width: 14px;
		text-align: center;
	}

	.stop-time-pill {
		background: #ffffff;
		padding: 7px 14px;
		border-radius: 999px;
		font-size: 0.98rem;
		font-weight: 700;
		color: #1a1a1a;
		box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
	}

	.stop-divider {
		width: 1.5px;
		height: 38px;
		background: #d8e5d5;
		margin: 0 14px;
		flex-shrink: 0;
	}

	.stop-info-col {
		flex: 1;
		min-width: 0;
	}

	.patient-name {
		font-size: 1.15rem;
		font-weight: 700;
		color: #1a1a1a;
		margin-bottom: 3px;
		line-height: 1.2;
	}

	.patient-address {
		display: flex;
		align-items: center;
		gap: 4px;
		font-size: 0.88rem;
		color: #444;
		line-height: 1.2;
	}

	.pin-icon {
		font-size: 0.95rem;
		flex-shrink: 0;
	}

	.stop-checkbox-col {
		margin-left: 12px;
		flex-shrink: 0;
	}

	.check-box {
		width: 32px;
		height: 32px;
		border-radius: 10px;
		border: 1.5px solid #1a1a1a;
		background: #ffffff;
		display: flex;
		align-items: center;
		justify-content: center;
		transition:
			background 0.2s,
			border-color 0.2s;
	}

	.check-box.checked {
		background: #5f9754;
		border-color: #5f9754;
	}

	.checkmark {
		color: #ffffff;
		font-size: 1.15rem;
		font-weight: 800;
		line-height: 1;
	}

	/* ─── Footer Stats Card ─────────────── */
	.route-footer-stats {
		background: #eff5ed;
		border-radius: 22px;
		padding: 20px 22px;
		display: flex;
		align-items: center;
		justify-content: space-between;
		margin-top: auto;
	}

	.stat-col {
		flex: 1;
		display: flex;
		flex-direction: column;
		justify-content: center;
	}

	.stat-col.left-col {
		padding-right: 14px;
	}

	.stat-col.right-col {
		padding-left: 14px;
	}

	.stat-title {
		font-size: 0.82rem;
		font-weight: 600;
		color: #333;
		margin-bottom: 6px;
		line-height: 1.3;
	}

	.stat-value-group {
		display: flex;
		align-items: baseline;
		gap: 6px;
	}

	.big-number {
		font-size: 2.5rem;
		font-weight: 800;
		color: #1a1a1a;
		line-height: 1;
	}

	.unit-text {
		font-size: 1.35rem;
		font-weight: 700;
		color: #1a1a1a;
	}

	.stat-vertical-divider {
		width: 1.5px;
		height: 58px;
		background: #cbdcc8;
		flex-shrink: 0;
	}

	.stat-time-display {
		font-size: 2.2rem;
		font-weight: 800;
		color: #1a1a1a;
		line-height: 1;
	}
</style>
