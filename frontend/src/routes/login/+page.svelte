<script lang="ts">
	import logo from '#lib/assets/opticare-logo.svg';
	import { login } from '#lib/stores/auth.js';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';

	let username = $state('');
	let password = $state('');
	let error = $state('');
	let loading = $state(false);

	function handleSubmit(e: SubmitEvent) {
		e.preventDefault();
		error = '';

		if (!username.trim()) {
			error = 'Unesite korisničko ime.';
			return;
		}
		if (!password.trim()) {
			error = 'Unesite lozinku.';
			return;
		}

		loading = true;
		// Frontend-only: prihvati bilo koje korisničko ime i lozinku
		setTimeout(() => {
			login(username.trim());
			goto(resolve('/'));
		}, 400);
	}
</script>

<svelte:head>
	<title>OptiCare — Prijava</title>
</svelte:head>

<div class="login-page">
	<div class="login-card">
		<div class="login-logo-wrap">
			<img src={logo} alt="OptiCare" class="login-logo" />
		</div>

		<h1 class="login-title">Prijava u sustav</h1>
		<p class="login-subtitle">Sustav planiranja prijevoza pacijenata</p>

		<form onsubmit={handleSubmit} class="login-form">
			<div class="form-group">
				<label class="form-label" for="username">Korisničko ime</label>
				<input
					id="username"
					class="form-input"
					type="text"
					bind:value={username}
					autocomplete="username"
					placeholder="Unesite korisničko ime"
				/>
			</div>

			<div class="form-group">
				<label class="form-label" for="password">Lozinka</label>
				<input
					id="password"
					class="form-input"
					type="password"
					bind:value={password}
					autocomplete="current-password"
					placeholder="Unesite lozinku"
				/>
			</div>

			{#if error}
				<p class="error-text">{error}</p>
			{/if}

			<button type="submit" class="btn-primary" disabled={loading}>
				{loading ? 'Prijava…' : 'Prijavi se'}
			</button>
		</form>
	</div>
</div>

<style>
	.login-page {
		min-height: 100dvh;
		display: flex;
		align-items: center;
		justify-content: center;
		background: var(--bg);
		padding: 24px;
	}

	.login-card {
		background: #fff;
		border: 1.5px solid var(--border);
		border-radius: 24px;
		padding: 48px 40px;
		width: 100%;
		max-width: 420px;
		box-shadow: 0 4px 24px rgba(0, 0, 0, 0.08);
	}

	.login-logo-wrap {
		display: flex;
		justify-content: center;
		margin-bottom: 32px;
	}

	.login-logo {
		height: 56px;
		width: auto;
	}

	.login-title {
		font-size: 1.8rem;
		font-weight: 800;
		text-align: center;
		margin-bottom: 6px;
		letter-spacing: -0.02em;
		color: var(--text);
	}

	.login-subtitle {
		text-align: center;
		font-size: 0.95rem;
		color: var(--text-muted);
		margin-bottom: 32px;
	}

	.login-form {
		display: flex;
		flex-direction: column;
		gap: 4px;
	}

	.btn-primary:disabled {
		opacity: 0.7;
		cursor: not-allowed;
	}
</style>
