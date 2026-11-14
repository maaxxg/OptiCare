<script lang="ts">
	import logo from '#lib/assets/opticare-logo.svg';
	import { getDriverState, isDriverLoggedIn, logoutDriver } from '#lib/stores/driver.js';
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

	function handleLogout() {
		logoutDriver();
		goto(resolve('/mobilno/login'));
	}

	function goToRoute() {
		goto(resolve('/mobilno/ruta'));
	}
</script>

<svelte:head>
	<title>OptiCare Mobilno — Početna</title>
</svelte:head>

<div class="mobile-container">
	<div class="mobile-screen">
		<!-- Gornji header: ime i odjava -->
		<div class="mobile-top-bar">
			<span class="driver-name-display">{driver.name || 'Ime i prezime'}</span>
			<button class="logout-link" onclick={handleLogout}>Odjava</button>
		</div>

		<!-- Središnji sadržaj -->
		<div class="mobile-center-content">
			<div class="mobile-logo-wrap">
				<img src={logo} alt="OptiCare" class="mobile-logo" />
			</div>

			<h1 class="mobile-title">Dobrodošli,</h1>
			<p class="mobile-subtitle">Pregledajte svoju rutu</p>

			<button class="schedule-action-btn" onclick={goToRoute}>
				<span>Raspored</span>
				<span>vožnje</span>
			</button>
		</div>

		<!-- Link za povratak na desktop -->
		<div class="desktop-switch-footer">
			<a href={resolve('/')} class="switch-link">← Povratak na dispečersku ploču</a>
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
		padding: 32px 28px;
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
			padding: 24px 22px;
		}
	}

	.mobile-top-bar {
		display: flex;
		justify-content: flex-end;
		align-items: center;
		gap: 12px;
		font-size: 0.95rem;
		padding-top: 4px;
	}

	.driver-name-display {
		color: #1a1a1a;
		font-weight: 500;
	}

	.logout-link {
		background: none;
		border: none;
		color: #1a4f8b;
		text-decoration: underline;
		font-size: 0.95rem;
		font-weight: 600;
		cursor: pointer;
		padding: 0;
	}

	.mobile-center-content {
		display: flex;
		flex-direction: column;
		align-items: center;
		margin-top: auto;
		margin-bottom: auto;
		width: 100%;
	}

	.mobile-logo-wrap {
		margin-bottom: 36px;
	}

	.mobile-logo {
		height: 48px;
		width: auto;
	}

	.mobile-title {
		font-size: 2.6rem;
		font-weight: 800;
		color: #000000;
		text-align: center;
		margin-bottom: 6px;
		letter-spacing: -0.02em;
	}

	.mobile-subtitle {
		font-size: 1.15rem;
		color: #1a1a1a;
		text-align: center;
		margin-bottom: 56px;
		font-weight: 500;
	}

	.schedule-action-btn {
		width: 82%;
		padding: 28px 20px;
		background: #8bbb82;
		color: #ffffff;
		border: 3.5px solid #1a1a1a;
		border-radius: 28px;
		font-size: 1.55rem;
		font-weight: 700;
		cursor: pointer;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 4px;
		box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
		transition:
			transform 0.1s,
			background 0.2s;
		line-height: 1.15;
	}

	.schedule-action-btn:hover {
		background: #7ca874;
	}

	.schedule-action-btn:active {
		transform: scale(0.97);
	}

	.desktop-switch-footer {
		text-align: center;
		padding-top: 20px;
	}

	.switch-link {
		font-size: 0.82rem;
		color: #777;
		text-decoration: underline;
	}
</style>
