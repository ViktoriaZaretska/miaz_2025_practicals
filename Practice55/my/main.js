import { mockData } from './mock.js';

// Генерація інформаційних карток
const infoCards = document.getElementById('info-cards');
const ranks = {};
mockData.groups.forEach(group => {
  group.students.forEach(student => {
    ranks[student.rank_name] = (ranks[student.rank_name] || 0) + 1;
  });
});

Object.entries(ranks).forEach(([rank, count]) => {
  const card = document.createElement('div');
  card.className = 'info-box';
  card.innerHTML = `<strong>${rank}</strong>: ${count}`;
  infoCards.appendChild(card);
});

// Графік по групам
const ctx = document.getElementById('chart1').getContext('2d');
new Chart(ctx, {
  type: 'bar',
  data: {
    labels: mockData.groups.map(g => g.group_name),
    datasets: [{
      label: 'Кількість військових',
      data: mockData.groups.map(g => g.students.length),
      backgroundColor: 'rgba(3, 83, 29, 0.6)',
      borderColor: 'rgb(2, 38, 10)',
      borderWidth: 1
    }]
  },
  options: {
    scales: {
      y: { beginAtZero: true }
    }
  }
});

// Заповнення таблиці
// const tbody = document.querySelector('#student-table tbody');
// mockData.groups.forEach(group => {
//   group.students.forEach(student => {
//     const row = document.createElement('tr');
//     row.innerHTML = `
//       <td class="p-2">${student.full_name}</td>
//       <td class="p-2">${student.birth_date}</td>
//       <td class="p-2">${student.rank_name}</td>
//       <td class="p-2">${group.group_name}</td>
//     `;
//     tbody.appendChild(row);
//   });
// });

// Ініціалізація карти
const map = L.map('map').setView([48.3794, 31.1656], 6); // Центр України
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);

// Приклад маркерів для груп (можна замінити реальними даними)
const locations = [
  { coords: [50.4501, 30.5234], group: 'Group A' }, // Київ
  { coords: [49.8397, 24.0297], group: 'Group B' }, // Львів
  { coords: [46.4825, 30.7233], group: 'Group C' }, // Одеса
];

locations.forEach(loc => {
  L.marker(loc.coords).addTo(map).bindPopup(loc.group);
});



