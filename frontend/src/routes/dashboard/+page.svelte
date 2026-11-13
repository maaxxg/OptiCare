<script lang="ts">
	import { getUser, logout } from '#lib/stores/auth';
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';

	let user = $state(getUser());

	onMount(() => {
		user = getUser();
		if (!user) {
			goto('/');
		}
	});

	function handleLogout() {
		logout();
		goto('/');
	}
</script>

<svelte:head>
	<title>OptiCare — Početna</title>
</svelte:head>

{#if user}
	<div class="page">
		<div class="page-header">
			<div class="logo-dot"></div>
			<div class="page-header-right">
				<span>{user.name}</span>
				<!-- svelte-ignore a11y_invalid_attribute -->
				<a href="#" onclick={handleLogout}>Odjava</a>
			</div>
		</div>

		<h1 class="page-title">Dobro došli</h1>

		<div class="dashboard-actions">
			<a href="/unos" class="action-card">Unos informacija pacijenta</a>
			<a href="/raspored" class="action-card">Raspored</a>
		</div>
	</div>
{/if}

<style>
	.dashboard-actions {
		margin-top: 40px;
		display: flex;
		flex-direction: column;
		gap: 16px;
	}
</style>
