<script lang="ts">
	import { login } from "#lib/stores/auth";
	import { goto } from "$app/navigation";

	let name = $state("");
	let role = $state("");
	let hospital = $state("");
	let error = $state("");

	const roles = ["Medicinska sestra", "Vozač"];

	const hospitals = [
		"Opća bolnica Gospić",
		"Dom zdravlja Gospić",
		"Dom zdravlja Otočac",
		"Dom zdravlja Senj",
		"Dom zdravlja Korenica",
		"Dom zdravlja Novalja",
	];

	function handleSubmit(e: SubmitEvent) {
		e.preventDefault();
		error = "";

		if (!name.trim()) {
			error = "Unesite ime i prezime.";
			return;
		}
		if (!role) {
			error = "Odaberite zanimanje.";
			return;
		}
		if (!hospital) {
			error = "Odaberite bolnicu.";
			return;
		}

		login(name.trim(), role, hospital);
		goto("/dashboard");
	}
</script>

<svelte:head>
	<title>OptiCare — Prijava</title>
</svelte:head>

<div class="page">
	<div class="page-header">
		<div class="logo-dot"></div>
	</div>

	<h1 class="page-title">Dobro došli</h1>
	<p class="page-subtitle">Prijavite se u sustav</p>

	<form onsubmit={handleSubmit}>
		<div class="form-group">
			<label class="form-label" for="name">Ime i prezime</label>
			<input
				id="name"
				class="form-input"
				type="text"
				bind:value={name}
				autocomplete="name"
			/>
		</div>

		<div class="form-group">
			<label class="form-label" for="role">Zanimanje</label>
			<select id="role" class="form-select" bind:value={role}>
				<option value="" disabled selected hidden></option>
				{#each roles as r}
					<option value={r}>{r}</option>
				{/each}
			</select>
		</div>

		<div class="form-group">
			<label class="form-label" for="hospital">Bolnica</label>
			<select id="hospital" class="form-select" bind:value={hospital}>
				<option value="" disabled selected hidden></option>
				{#each hospitals as h}
					<option value={h}>{h}</option>
				{/each}
			</select>
		</div>

		{#if error}
			<p class="error-text">{error}</p>
		{/if}

		<button type="submit" class="btn-primary">Prijavite se</button>
	</form>
</div>

<style>
	.error-text {
		color: #c0392b;
		font-size: 0.88rem;
		margin-bottom: 16px;
		text-align: center;
	}
</style>
