<script lang="ts">
	import logo from '#lib/assets/opticare-logo.svg';
	import { getDoctorName, logout } from '#lib/stores/auth.js';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';

	const doctorName = getDoctorName();

	function handleLogout() {
		logout();
		goto(resolve('/login'));
	}
</script>

<svelte:head>
	<title>OptiCare</title>
</svelte:head>

<div class="page">
	<div class="page-header">
		<img src={logo} alt="OptiCare" class="logo-full" />
		<div class="page-header-right">
			{#if doctorName}
				<span class="doctor-name">{doctorName}</span>
			{/if}
			<button class="logout-btn" onclick={handleLogout}>Odjava</button>
		</div>
	</div>

	<h1 class="page-title">Dobro došli</h1>
	<p class="page-subtitle">Planiranje termina i prijevoza za pacijente</p>

	<div class="dashboard-actions">
		<a href={resolve('/unos')} class="action-card">Unos podataka o pacijentu</a>
		<a href={resolve('/raspored')} class="action-card">Raspored</a>
		<a href={resolve('/mobilno')} class="action-card action-card-mobile"
			>📱 Mobilno sučelje (za vozače)</a
		>
	</div>
</div>

<style>
	.dashboard-actions {
		margin-top: 40px;
		display: flex;
		flex-direction: column;
		gap: 16px;
	}

	.action-card-mobile {
		background: #ffffff;
		color: #2e6226;
		border: 2px dashed #92c18b;
	}

	.action-card-mobile:hover {
		background: #e8eed9;
	}

	.doctor-name {
		font-size: 0.9rem;
		color: var(--text-muted);
		font-weight: 500;
	}

	.logout-btn {
		background: none;
		border: 1.5px solid var(--border);
		border-radius: var(--radius-pill);
		padding: 6px 16px;
		font-size: 0.85rem;
		font-family: var(--font-sans);
		color: var(--text);
		cursor: pointer;
		transition: background 0.2s;
	}

	.logout-btn:hover {
		background: var(--green-light);
	}
</style>
