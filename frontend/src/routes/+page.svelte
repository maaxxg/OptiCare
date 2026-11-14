<script lang="ts">
	import { resolve } from '$app/paths';
</script>

<svelte:head>
	<title>OptiCare</title>
</svelte:head>

<div class="page">
	<div class="page-header">
		<div class="logo-dot"></div>
	</div>

	<h1 class="page-title">Dobro došli</h1>
	<p class="page-subtitle">Planiranje termina i prijevoza za pacijente</p>

	<div class="dashboard-actions">
		<a href={resolve('/unos')} class="action-card">Unos informacija pacijenta</a>
		<a href={resolve('/raspored')} class="action-card">Raspored</a>
	</div>
</div>

<style>
	.dashboard-actions {
		margin-top: 40px;
		display: flex;
		flex-direction: column;
		gap: 16px;
	}
</style>
