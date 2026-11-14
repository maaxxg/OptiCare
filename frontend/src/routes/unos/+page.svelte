<script lang="ts">
	import { addPatient } from '#lib/stores/patients.js';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { onDestroy } from 'svelte';

	let name = $state('');
	let location = $state('');
	let needsTransport = $state(false);
	let willingToDrive = $state(false);
	let description = $state('');
	let error = $state('');
	let showToast = $state(false);
	let toastTimer: ReturnType<typeof setTimeout> | undefined;

	onDestroy(() => clearTimeout(toastTimer));

	const locations = [
		'Gospić',
		'Otočac',
		'Senj',
		'Korenica',
		'Novalja',
		'Perušić',
		'Brinje',
		'Donji Lapac',
		'Vrhovine',
		'Udbina',
		'Plitvička Jezera',
		'Lovinac',
		'Karlobag'
	];

	function handleSubmit(e: SubmitEvent) {
		e.preventDefault();
		error = '';

		if (!name.trim()) {
			error = 'Unesite ime i prezime pacijenta.';
			return;
		}
		if (!location) {
			error = 'Odaberite mjesto stanovanja.';
			return;
		}
		if (!description.trim()) {
			error = 'Unesite opis pacijentovog problema.';
			return;
		}

		addPatient({
			name: name.trim(),
			location,
			needsTransport,
			willingToDrive,
			description: description.trim()
		});

		// Reset form
		name = '';
		location = '';
		needsTransport = false;
		willingToDrive = false;
		description = '';

		// Show toast
		showToast = true;
		clearTimeout(toastTimer);
		toastTimer = setTimeout(() => {
			showToast = false;
		}, 2500);
	}

	function goBack() {
		goto(resolve('/'));
	}
</script>

<svelte:head>
	<title>OptiCare — Unos pacijenta</title>
</svelte:head>

<div class="page">
	<div class="page-header">
		<div class="logo-dot"></div>
		<button class="back-link" onclick={goBack}> Povratak ← </button>
	</div>

	<h1 class="page-title">Ispunite pacijentove podatke</h1>

	<form onsubmit={handleSubmit} class="intake-form">
		<div class="two-col">
			<div>
				<div class="form-group">
					<label class="form-label" for="patient-name">Ime i prezime</label>
					<input id="patient-name" class="form-input" type="text" bind:value={name} />
				</div>

				<div class="form-group">
					<label class="form-label" for="location">Mjesto stanovanja</label>
					<select id="location" class="form-select" bind:value={location}>
						<option value="" disabled selected hidden></option>
						{#each locations as loc (loc)}
							<option value={loc}>{loc}</option>
						{/each}
					</select>
				</div>
			</div>

			<div class="radio-box">
				<div class="radio-box-header-row">
					<span class="radio-box-spacer"></span>
					<div class="radio-cols-header">
						<span class="col-head">Da</span>
						<span class="col-head">Ne</span>
					</div>
				</div>

				<div class="radio-box-row">
					<span class="radio-box-label">Prijevoz</span>
					<div class="radio-cols-options">
						<label class="radio-cell">
							<input
								type="radio"
								name="transport"
								value="true"
								checked={needsTransport === true}
								onchange={() => (needsTransport = true)}
							/>
						</label>
						<label class="radio-cell">
							<input
								type="radio"
								name="transport"
								value="false"
								checked={needsTransport === false}
								onchange={() => (needsTransport = false)}
							/>
						</label>
					</div>
				</div>

				<div class="radio-box-row">
					<span class="radio-box-label">Voljan voziti drugu osobu</span>
					<div class="radio-cols-options">
						<label class="radio-cell">
							<input
								type="radio"
								name="willing"
								value="true"
								checked={willingToDrive === true}
								onchange={() => (willingToDrive = true)}
							/>
						</label>
						<label class="radio-cell">
							<input
								type="radio"
								name="willing"
								value="false"
								checked={willingToDrive === false}
								onchange={() => (willingToDrive = false)}
							/>
						</label>
					</div>
				</div>
			</div>
		</div>

		<div class="form-group" style="margin-top: 20px;">
			<label class="form-label" for="description">Opis pacijentovog problema</label>
			<textarea id="description" class="form-textarea" bind:value={description}></textarea>
		</div>

		{#if error}
			<p class="error-text">{error}</p>
		{/if}

		<button type="submit" class="btn-primary">Predaj</button>
	</form>
</div>

{#if showToast}
	<div class="toast">✓ Pacijent uspješno dodan</div>
{/if}

<style>
	.intake-form {
		margin-top: 24px;
	}
</style>
