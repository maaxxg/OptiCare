<script lang="ts">
	import { getUser } from "#lib/stores/auth";
	import { getPatients } from "#lib/stores/patients";
	import { goto } from "$app/navigation";
	import { onMount } from "svelte";

	let user = $state(getUser());
	let patients = $state(getPatients());
	let selectedDate = $state("Subota, 14. Studenoga");

	onMount(() => {
		user = getUser();
		patients = getPatients();
		if (!user) {
			goto("/");
		}
	});

	function goBack() {
		goto("/dashboard");
	}

	interface ScheduleRow {
		firstName: string;
		lastName: string;
		examType: string;
		clinic: string;
		examTime: string;
		departureTime: string;
		arrivalTime: string;
	}

	// Initial mock rows from design
	const baseGroup1: ScheduleRow[] = [
		{
			firstName: "Petar",
			lastName: "Šavorić",
			examType: "Kardiološki pregled",
			clinic: "KBC Rebro",
			examTime: "10:00",
			departureTime: "7:30",
			arrivalTime: "16:00",
		},
		{
			firstName: "Vili",
			lastName: "Cenko",
			examType: "Pregled mikropenisa",
			clinic: "KBC Rebro",
			examTime: "12:00",
			departureTime: "7:30",
			arrivalTime: "16:00",
		},
	];

	const baseGroup2: ScheduleRow[] = [
		{
			firstName: "Petar",
			lastName: "Šavorić",
			examType: "Kardiološki pregled",
			clinic: "KBC Rebro",
			examTime: "10:00",
			departureTime: "7:30",
			arrivalTime: "16:00",
		},
		{
			firstName: "Vili",
			lastName: "Cenko",
			examType: "Pregled mikropenisa",
			clinic: "KBC Rebro",
			examTime: "12:00",
			departureTime: "7:30",
			arrivalTime: "16:00",
		},
	];

	const baseGroup3: ScheduleRow[] = [
		{
			firstName: "Petar",
			lastName: "Šavorić",
			examType: "Kardiološki pregled",
			clinic: "KBC Rebro",
			examTime: "10:00",
			departureTime: "7:30",
			arrivalTime: "16:00",
		},
	];

	// Derived lists merging store patients if any
	const group1Rows = $derived([
		...baseGroup1,
		...patients
			.filter((p) => p.needsTransport && !p.willingToDrive)
			.map((p) => {
				const parts = p.name.split(" ");
				return {
					firstName: parts[0] || p.name,
					lastName: parts.slice(1).join(" ") || "",
					examType: p.description.slice(0, 30) || "Pregled",
					clinic: p.location || "Opća bolnica Gospić",
					examTime: "11:00",
					departureTime: "8:00",
					arrivalTime: "15:30",
				};
			}),
	]);

	const group2Rows = $derived([
		...baseGroup2,
		...patients
			.filter((p) => p.willingToDrive)
			.map((p) => {
				const parts = p.name.split(" ");
				return {
					firstName: parts[0] || p.name,
					lastName: parts.slice(1).join(" ") || "",
					examType: p.description.slice(0, 30) || "Pregled",
					clinic: p.location || "Opća bolnica Gospić",
					examTime: "10:30",
					departureTime: "8:00",
					arrivalTime: "15:30",
				};
			}),
	]);

	const group3Rows = $derived([
		...baseGroup3,
		...patients
			.filter((p) => !p.needsTransport && !p.willingToDrive)
			.map((p) => {
				const parts = p.name.split(" ");
				return {
					firstName: parts[0] || p.name,
					lastName: parts.slice(1).join(" ") || "",
					examType: p.description.slice(0, 30) || "Pregled",
					clinic: p.location || "Opća bolnica Gospić",
					examTime: "09:00",
					departureTime: "7:00",
					arrivalTime: "14:00",
				};
			}),
	]);
</script>

<svelte:head>
	<title>OptiCare — Raspored pacijenata</title>
</svelte:head>

{#if user}
	<div class="page-wide">
		<div class="schedule-top-nav">
			<div class="logo-dot"></div>
			<button class="back-link" onclick={goBack}> Povratak ← </button>
		</div>

		<div class="schedule-header-row">
			<h1 class="schedule-main-title">Raspored pacijenata</h1>

			<div class="schedule-controls">
				<button class="date-pill" type="button">
					{selectedDate}
					<span class="chevron-down"></span>
				</button>
				<button
					class="circle-nav-btn"
					type="button"
					aria-label="Prethodni dan">&lt;</button
				>
				<button
					class="circle-nav-btn"
					type="button"
					aria-label="Sljedeći dan">&gt;</button
				>
			</div>
		</div>

		<div class="schedule-legend">
			<div class="legend-item">
				<div class="legend-square green"></div>
				<span>Osiguran prijevoz</span>
			</div>
			<div class="legend-item">
				<div class="legend-square blue"></div>
				<span>Osiguran prijevoz, stane još pacijenata</span>
			</div>
			<div class="legend-item">
				<div class="legend-square peach"></div>
				<span>Nema prijevoz</span>
			</div>
		</div>

		<div class="schedule-table-wrap">
			<div class="schedule-table">
				<div class="table-header-pill">
					<span>Osoba</span>
					<span>Vrsta pregleda</span>
					<span>Ordinacija</span>
					<span class="center-col">Polazak</span>
					<span class="center-col">Vrijeme pregleda</span>
					<span class="center-col">Povratak</span>
				</div>

				<!-- Grupa 1: Osiguran prijevoz -->
				<section class="schedule-group">
					<div class="group-title green">Osiguran prijevoz</div>
					<div class="group-container green">
						{#each group1Rows as row}
							<div class="schedule-row">
								<div class="col-person">
									{row.firstName}<br />{row.lastName}
								</div>
								<div class="col-exam">{row.examType}</div>
								<div class="col-clinic">{row.clinic}</div>
								<span class="center-col">
									<span class="time-badge-pill">{row.departureTime}</span>
								</span>
								<span class="center-col">
									<span class="time-badge-pill">{row.examTime}</span>
								</span>
								<span class="center-col">
									<span class="time-badge-pill">{row.arrivalTime}</span>
								</span>
							</div>
						{/each}
					</div>
				</section>

				<!-- Grupa 2: Osiguran prijevoz - dodatna slobona mjesta -->
				<section class="schedule-group">
					<div class="group-title blue">
						Osiguran prijevoz - dodatna slobona mjesta
					</div>
					<div class="group-container blue">
						{#each group2Rows as row}
							<div class="schedule-row">
								<div class="col-person">
									{row.firstName}<br />{row.lastName}
								</div>
								<div class="col-exam">{row.examType}</div>
								<div class="col-clinic">{row.clinic}</div>
								<span class="center-col">
									<span class="time-badge-pill">{row.departureTime}</span>
								</span>
								<span class="center-col">
									<span class="time-badge-pill">{row.examTime}</span>
								</span>
								<span class="center-col">
									<span class="time-badge-pill">{row.arrivalTime}</span>
								</span>
							</div>
						{/each}
					</div>
				</section>

				<!-- Grupa 3: Nema prijevoz -->
				<section class="schedule-group">
					<div class="group-title peach">Nema prijevoz</div>
					<div class="group-container peach">
						{#each group3Rows as row}
							<div class="schedule-row">
								<div class="col-person">
									{row.firstName}<br />{row.lastName}
								</div>
								<div class="col-exam">{row.examType}</div>
								<div class="col-clinic">{row.clinic}</div>
								<span class="center-col">
									<span class="time-badge-pill">{row.departureTime}</span>
								</span>
								<span class="center-col">
									<span class="time-badge-pill">{row.examTime}</span>
								</span>
								<span class="center-col">
									<span class="time-badge-pill">{row.arrivalTime}</span>
								</span>
							</div>
						{/each}
					</div>
				</section>
			</div>
		</div>
	</div>
{/if}
