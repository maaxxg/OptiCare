<script lang="ts">
	import logo from '#lib/assets/opticare-logo.svg';
	import { loginDriver } from '#lib/stores/driver.js';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';

	let name = $state('');
	let profession = $state('Vozač');
	let hospital = $state('Opća bolnica Gospić');
	let error = $state('');

	const professions = ['Vozač', 'Sanitetski prijevoznik', 'Vozač volonter', 'Patronažna sestra'];

	const hospitals = [
		'Opća bolnica Gospić',
		'KBC Rebro',
		'KBC Rijeka',
		'KBC Sestre milosrdnice',
		'Dom zdravlja Otočac',
		'Dom zdravlja Korenica'
	];

	function handleLogin(e: SubmitEvent) {
		e.preventDefault();
		if (!name.trim()) {
			error = 'Molimo unesite ime i prezime.';
			return;
		}
		loginDriver(name.trim(), profession, hospital);
		goto(resolve('/mobilno'));
	}
</script>

<svelte:head>
	<title>OptiCare Mobilno — Prijava</title>
</svelte:head>

<div class="mobile-container">
	<div class="mobile-screen">
		<!-- Desktop povratak link -->
		<div class="desktop-switch-bar">
			<a href={resolve('/')} class="switch-link">← Povratak na glavno računalo</a>
		</div>

		<div class="mobile-logo-wrap">
			<img src={logo} alt="OptiCare" class="mobile-logo" />
		</div>

		<h1 class="mobile-title">Dobrodošli,</h1>
		<p class="mobile-subtitle">Prijavite se u sustav</p>

		<form onsubmit={handleLogin} class="mobile-form">
			<div class="mobile-field">
				<label class="mobile-label" for="driver-name">Ime i prezime</label>
				<input
					id="driver-name"
					class="mobile-input"
					type="text"
					bind:value={name}
					placeholder="Unesite ime i prezime"
				/>
			</div>

			<div class="mobile-field">
				<label class="mobile-label" for="driver-prof">Zanimanje</label>
				<select id="driver-prof" class="mobile-select" bind:value={profession}>
					{#each professions as p (p)}
						<option value={p}>{p}</option>
					{/each}
				</select>
			</div>

			<div class="mobile-field">
				<label class="mobile-label" for="driver-hosp">Bolnica</label>
				<select id="driver-hosp" class="mobile-select" bind:value={hospital}>
					{#each hospitals as h (h)}
						<option value={h}>{h}</option>
					{/each}
				</select>
			</div>

			{#if error}
				<p class="mobile-error">{error}</p>
			{/if}

			<button type="submit" class="mobile-submit-btn"> Prijavite se </button>
		</form>
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
		padding: 36px 30px 48px;
		border-radius: 40px;
		box-shadow: 0 12px 36px rgba(0, 0, 0, 0.12);
		border: 8px solid #1a1a1a;
		display: flex;
		flex-direction: column;
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
			padding: 24px 22px 36px;
		}
	}

	.desktop-switch-bar {
		margin-bottom: 24px;
		text-align: center;
	}

	.switch-link {
		font-size: 0.8rem;
		color: #666;
		text-decoration: underline;
		cursor: pointer;
	}

	.mobile-logo-wrap {
		display: flex;
		justify-content: center;
		margin-top: 10px;
		margin-bottom: 24px;
	}

	.mobile-logo {
		height: 46px;
		width: auto;
	}

	.mobile-title {
		font-size: 2.3rem;
		font-weight: 800;
		color: #000000;
		text-align: center;
		margin-bottom: 2px;
		letter-spacing: -0.02em;
		line-height: 1.1;
	}

	.mobile-subtitle {
		font-size: 1.05rem;
		color: #1a1a1a;
		text-align: center;
		margin-bottom: 34px;
		font-weight: 500;
	}

	.mobile-form {
		display: flex;
		flex-direction: column;
		gap: 22px;
		flex: 1;
	}

	.mobile-field {
		display: flex;
		flex-direction: column;
		gap: 8px;
	}

	.mobile-label {
		color: #6b9e64;
		font-size: 1.05rem;
		font-weight: 600;
		padding-left: 6px;
	}

	.mobile-input,
	.mobile-select {
		width: 100%;
		padding: 15px 22px;
		background: #eef5ec;
		border: 1.5px solid #1a1a1a;
		border-radius: 999px;
		font-size: 1.05rem;
		font-family: inherit;
		color: #1a1a1a;
		outline: none;
		box-sizing: border-box;
		transition: border-color 0.2s;
	}

	.mobile-input:focus,
	.mobile-select:focus {
		border-color: #6b9e64;
		background: #ffffff;
	}

	.mobile-select {
		appearance: none;
		background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='18' height='18' viewBox='0 0 24 24' fill='none' stroke='%231a1a1a' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='6 9 12 15 18 9'%3E%3C/polyline%3E%3C/svg%3E");
		background-repeat: no-repeat;
		background-position: right 20px center;
		padding-right: 48px;
		cursor: pointer;
	}

	.mobile-error {
		color: #d32f2f;
		font-size: 0.9rem;
		text-align: center;
	}

	.mobile-submit-btn {
		margin-top: 18px;
		width: 100%;
		padding: 16px 20px;
		background: #609756;
		color: #ffffff;
		border: 2px solid #1a1a1a;
		border-radius: 999px;
		font-size: 1.35rem;
		font-weight: 700;
		font-family: inherit;
		cursor: pointer;
		box-shadow: 0 4px 12px rgba(96, 151, 86, 0.25);
		transition:
			transform 0.1s,
			background 0.2s;
	}

	.mobile-submit-btn:hover {
		background: #528349;
	}

	.mobile-submit-btn:active {
		transform: scale(0.98);
	}
</style>
